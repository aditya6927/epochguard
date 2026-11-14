package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"os"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/maximhq/bifrost/core/schemas"
)

const receiptVersion = "004d.v1"
const receiptPolicy = "004b.v1/multi-claim-templates-v1"
const nonceHeader = "X-EpochGuard-Internal-Nonce"
const receiptHeader = "X-EpochGuard-Internal-Receipt"

type attestationConfig struct {
	Protocol   string `json:"protocol"`
	SecretFile string `json:"secret_file"`
}
type attestationKey struct{ secret []byte }
type attestationState struct {
	policy                                         *policy
	nonce, outcome, candidate, code, kind, message string
	status                                         int
}
type enforcementReceipt struct {
	Version         string `json:"version"`
	Nonce           string `json:"nonce"`
	PolicyID        string `json:"policy_id"`
	Outcome         string `json:"outcome"`
	Status          int    `json:"status"`
	BodySHA256      string `json:"body_sha256"`
	CandidateSHA256 string `json:"candidate_sha256"`
	IssuedAt        int64  `json:"issued_at"`
}

func loadAttestation(cfg attestationConfig) (*attestationKey, error) {
	if cfg.Protocol != receiptVersion || cfg.SecretFile == "" {
		return nil, errors.New("invalid attestation configuration")
	}
	f, err := os.Open(cfg.SecretFile)
	if err != nil {
		return nil, errors.New("secret unavailable")
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, 67))
	if err != nil {
		return nil, errors.New("secret unavailable")
	}
	text := strings.TrimSuffix(strings.TrimSuffix(string(data), "\n"), "\r")
	if !digestRE.MatchString(text) {
		return nil, errors.New("invalid secret")
	}
	key, _ := hex.DecodeString(text)
	return &attestationKey{key}, nil
}

func beginAttestation(ctx *schemas.BifrostContext, req *schemas.HTTPRequest) {
	p := activePolicy.Load()
	if p == nil || p.attestation == nil || req == nil || req.Method != "POST" || req.Path != "/openai/v1/chat/completions" || len(req.Query) != 0 {
		return
	}
	nonce := req.CaseInsensitiveHeaderLookup(nonceHeader)
	if !digestRE.MatchString(nonce) {
		return
	}
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return
	}
	trace.mu.Lock()
	trace.attested = &attestationState{policy: p, nonce: nonce}
	trace.mu.Unlock()
}

func recordAttestation(ctx *schemas.BifrostContext, p *policy, original *schemas.BifrostResponse, upstream *schemas.BifrostError, out *schemas.BifrostResponse, failure *schemas.BifrostError) {
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return
	}
	trace.mu.Lock()
	defer trace.mu.Unlock()
	s := trace.attested
	if s == nil {
		return
	}
	// Every fallback attempt replaces the prior attempt's result. Snapshot only
	// bounded strings/integers, never borrowed Bifrost response/error pointers.
	s.outcome, s.candidate, s.code, s.kind, s.message, s.status = "", "", "", "", "", 0
	if p == nil || p != s.policy || activePolicy.Load() != p || ctx.Err() != nil {
		return
	}
	if upstream == nil && failure == nil && out != nil && out == original {
		text, err := bufferedCandidate(out)
		if err == nil && multiTextBound(text) {
			s.outcome, s.candidate, s.status = "ALLOW", strings.Clone(text), 200
		}
		return
	}
	if out != nil || failure == nil || failure.Error == nil {
		return
	}
	status := failure.EffectiveHTTPStatus()
	if status < 400 || status > 599 {
		return
	}
	if upstream != nil {
		if failure != upstream || upstream.IsBifrostError {
			return
		}
		s.outcome = "PROVIDER_ERROR"
	} else if failure.Error.Code != nil && *failure.Error.Code == "epochguard_rejected" && status == 403 {
		s.outcome = "REJECT"
	} else if failure.Error.Code != nil && *failure.Error.Code == "epochguard_verification_unavailable" && status == 503 {
		s.outcome = "UNAVAILABLE"
	} else {
		return
	}
	if len(failure.Error.Message) > 2048 {
		s.outcome = ""
		return
	}
	s.status, s.message = status, strings.Clone(failure.Error.Message)
	if failure.Error.Code != nil {
		s.code = strings.Clone(*failure.Error.Code)
	}
	if failure.Error.Type != nil {
		s.kind = strings.Clone(*failure.Error.Type)
	}
	if len(s.code) > 128 || len(s.kind) > 128 {
		s.outcome = ""
	}
}

func finishAttestation(ctx *schemas.BifrostContext, resp *schemas.HTTPResponse) {
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return
	}
	trace.mu.Lock()
	defer trace.mu.Unlock()
	active := activePolicy.Load()
	if trace.attested == nil && (active == nil || active.attestation == nil) {
		return
	}
	// Always remove preexisting receipts in this hook's snapshot. Later writers
	// remain untrusted: ingress checks the MAC against the bytes it actually read.
	for key := range resp.Headers {
		if strings.HasPrefix(strings.ToLower(key), "x-epochguard-internal-") {
			delete(resp.Headers, key)
		}
	}
	s := trace.attested
	if s == nil || s.outcome == "" || s.policy != activePolicy.Load() || resp.StatusCode != s.status || len(resp.Body) == 0 || len(resp.Body) > 256*1024 {
		return
	}
	media := ""
	for key, value := range resp.Headers {
		if strings.EqualFold(key, "Content-Type") {
			media, _, _ = mime.ParseMediaType(value)
		}
		if strings.EqualFold(key, "Content-Encoding") && value != "" && value != "identity" {
			return
		}
	}
	if media != "application/json" || !attestedBody(resp.Body, s) {
		return
	}
	candidateHash := ""
	if s.outcome == "ALLOW" {
		candidateHash = shaText(s.candidate)
	}
	r := enforcementReceipt{receiptVersion, s.nonce, receiptPolicy, s.outcome, s.status, shaText(string(resp.Body)), candidateHash, time.Now().Unix()}
	payload, err := json.Marshal(r)
	if err != nil {
		return
	}
	mac := hmac.New(sha256.New, s.policy.attestation.secret)
	_, _ = mac.Write(payload)
	resp.Headers[receiptHeader] = base64.RawURLEncoding.EncodeToString(payload) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// Validate the post-conversion protected content before binding final bytes.
// Unknown body fields, raw payloads, aliases, duplicates and extra answer forms
// are refused. Transport-owned bounded metadata is not an additional claim.
func attestedBody(data []byte, s *attestationState) bool {
	if !utf8.Valid(data) || !uniqueWireJSON(data) {
		return false
	}
	var root map[string]json.RawMessage
	if json.Unmarshal(data, &root) != nil {
		return false
	}
	if s.outcome != "ALLOW" {
		if !onlyWireKeys(root, "event_id", "type", "is_bifrost_error", "status_code", "error", "extra_fields") {
			return false
		}
		var e struct{ Code, Type, Message string }
		var fields map[string]json.RawMessage
		if json.Unmarshal(root["error"], &fields) != nil || !onlyWireKeys(fields, "code", "type", "message") || json.Unmarshal(root["error"], &e) != nil {
			return false
		}
		if raw, ok := root["status_code"]; ok {
			var status int
			if json.Unmarshal(raw, &status) != nil || status != s.status {
				return false
			}
		}
		return e.Code == s.code && e.Type == s.kind && e.Message == s.message && safeExtra(root["extra_fields"])
	}
	if !onlyWireKeys(root, "id", "object", "created", "model", "system_fingerprint", "service_tier", "choices", "usage", "extra_fields") {
		return false
	}
	var object string
	if json.Unmarshal(root["object"], &object) != nil || object != "chat.completion" {
		return false
	}
	var choices []map[string]json.RawMessage
	if json.Unmarshal(root["choices"], &choices) != nil || len(choices) != 1 || !onlyWireKeys(choices[0], "index", "finish_reason", "message", "logprobs") {
		return false
	}
	choice := choices[0]
	if raw, ok := root["created"]; ok {
		var created int64
		if json.Unmarshal(raw, &created) != nil || created < 0 {
			return false
		}
	}
	if raw, ok := choice["index"]; ok {
		var index int
		if json.Unmarshal(raw, &index) != nil || index != 0 {
			return false
		}
	}
	var reason string
	if json.Unmarshal(choice["finish_reason"], &reason) != nil || reason != "stop" {
		return false
	}
	if raw, ok := choice["logprobs"]; ok && string(raw) != "null" {
		return false
	}
	var message map[string]json.RawMessage
	if json.Unmarshal(choice["message"], &message) != nil || len(message) != 2 || !onlyWireKeys(message, "role", "content") {
		return false
	}
	var role, content string
	if json.Unmarshal(message["role"], &role) != nil || json.Unmarshal(message["content"], &content) != nil || role != "assistant" || content != s.candidate {
		return false
	}
	for _, key := range []string{"id", "model", "system_fingerprint", "service_tier"} {
		if raw, ok := root[key]; ok && string(raw) != "null" {
			var v string
			if json.Unmarshal(raw, &v) != nil || len(v) > 256 {
				return false
			}
		}
	}
	return numericWire(root["usage"], 0) && safeExtra(root["extra_fields"])
}

func onlyWireKeys(value map[string]json.RawMessage, keys ...string) bool {
	for key := range value {
		found := false
		for _, allowed := range keys {
			if key == allowed {
				found = true
			}
		}
		if !found {
			return false
		}
	}
	return true
}
func safeExtra(data []byte) bool {
	if len(data) == 0 || string(data) == "null" {
		return true
	}
	var value map[string]json.RawMessage
	if json.Unmarshal(data, &value) != nil || !onlyWireKeys(value, "request_type", "provider", "original_model_requested", "resolved_model_used", "latency", "upstream_latency", "chunk_index", "routing_info") {
		return false
	}
	for key, raw := range value {
		if key == "routing_info" {
			var routing map[string]json.RawMessage
			if json.Unmarshal(raw, &routing) != nil || !onlyWireKeys(routing, "provider", "model", "key", "is_fallback", "primary_provider", "primary_model", "requested_provider", "requested_model") {
				return false
			}
			for field, item := range routing {
				if field == "is_fallback" {
					var b bool
					if json.Unmarshal(item, &b) != nil {
						return false
					}
				} else {
					var text string
					if json.Unmarshal(item, &text) != nil || len(text) > 256 {
						return false
					}
				}
			}
		} else if key == "latency" || key == "upstream_latency" || key == "chunk_index" {
			if !numericWire(raw, 0) {
				return false
			}
		} else {
			var text string
			if json.Unmarshal(raw, &text) != nil || len(text) > 256 {
				return false
			}
		}
	}
	return true
}
func numericWire(data []byte, depth int) bool {
	if len(data) == 0 || string(data) == "null" {
		return true
	}
	if depth > 4 {
		return false
	}
	if data[0] == '{' {
		var fields map[string]json.RawMessage
		if json.Unmarshal(data, &fields) != nil {
			return false
		}
		for _, raw := range fields {
			if !numericWire(raw, depth+1) {
				return false
			}
		}
		return true
	}
	var n json.Number
	return json.Unmarshal(data, &n) == nil && len(n.String()) < 40
}
func uniqueWireJSON(data []byte) bool {
	d := json.NewDecoder(bytes.NewReader(data))
	d.UseNumber()
	var walk func(int) bool
	walk = func(depth int) bool {
		if depth > 8 {
			return false
		}
		token, err := d.Token()
		if err != nil {
			return false
		}
		if mark, ok := token.(json.Delim); ok {
			if mark == '{' {
				seen := map[string]bool{}
				for d.More() {
					key, err := d.Token()
					name, ok := key.(string)
					if err != nil || !ok || seen[name] {
						return false
					}
					seen[name] = true
					if !walk(depth + 1) {
						return false
					}
				}
				end, err := d.Token()
				return err == nil && end == json.Delim('}')
			}
			if mark == '[' {
				for count := 0; d.More(); count++ {
					if count >= 64 || !walk(depth+1) {
						return false
					}
				}
				end, err := d.Token()
				return err == nil && end == json.Delim(']')
			}
			return false
		}
		return true
	}
	if !walk(0) {
		return false
	}
	_, err := d.Token()
	return err == io.EOF
}
