// Package ingress implements the narrowly scoped 004D buffered release boundary.
package ingress

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

const Path = "/openai/v1/chat/completions"
const NonceHeader = "X-EpochGuard-Internal-Nonce"
const ReceiptHeader = "X-EpochGuard-Internal-Receipt"
const Protocol = "004d.v1"
const Policy = "004b.v1/multi-claim-templates-v1"
const ResponseLimit = 256 * 1024

var digestRE = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Receipt struct {
	Version         string `json:"version"`
	Nonce           string `json:"nonce"`
	PolicyID        string `json:"policy_id"`
	Outcome         string `json:"outcome"`
	Status          int    `json:"status"`
	BodySHA256      string `json:"body_sha256"`
	CandidateSHA256 string `json:"candidate_sha256"`
	IssuedAt        int64  `json:"issued_at"`
}
type Config struct {
	Gateway         string
	Secret          []byte
	ManagementToken string
	ProbeCandidate  string
	Timeout         time.Duration
	MaxActive       int
}
type Handler struct {
	cfg    Config
	client *http.Client
	slots  chan struct{}
}

func New(cfg Config) (*Handler, error) {
	u, err := url.Parse(cfg.Gateway)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.Path != "" || u.RawQuery != "" || u.Fragment != "" || u.User != nil || len(cfg.Secret) != 32 || cfg.ManagementToken == "" || cfg.ProbeCandidate == "" {
		return nil, errors.New("invalid ingress configuration")
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = 8 * time.Second
	}
	if cfg.MaxActive == 0 {
		cfg.MaxActive = 16
	}
	if cfg.Timeout < 100*time.Millisecond || cfg.Timeout > 10*time.Second || cfg.MaxActive < 1 || cfg.MaxActive > 32 {
		return nil, errors.New("invalid ingress bounds")
	}
	cfg.Secret = append([]byte(nil), cfg.Secret...)
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy, transport.DisableCompression = nil, true
	transport.MaxConnsPerHost, transport.MaxIdleConnsPerHost = cfg.MaxActive, cfg.MaxActive
	transport.IdleConnTimeout = 30 * time.Second
	return &Handler{cfg: cfg, slots: make(chan struct{}, cfg.MaxActive), client: &http.Client{Transport: transport, Timeout: cfg.Timeout, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}, nil
}
func (h *Handler) Close()     { h.client.CloseIdleConnections() }
func Hash(data []byte) string { sum := sha256.Sum256(data); return hex.EncodeToString(sum[:]) }

// A fresh per-call nonce provides replay protection without an unbounded global
// replay cache. Receipt bytes belong to this one buffered round trip only.
func (h *Handler) exchange(ctx context.Context, data []byte) (int, []byte, Receipt, error) {
	var receipt Receipt
	started := time.Now()
	nonceBytes := make([]byte, 32)
	if _, err := rand.Read(nonceBytes); err != nil {
		return 0, nil, receipt, errors.New("nonce unavailable")
	}
	nonce := hex.EncodeToString(nonceBytes)
	req, err := http.NewRequestWithContext(ctx, "POST", h.cfg.Gateway+Path, bytes.NewReader(data))
	if err != nil {
		return 0, nil, receipt, errors.New("request unavailable")
	}
	// No client header is forwarded. In particular nonce/receipt, raw-response,
	// bypass, auth, async and management headers cannot enter this trusted hop.
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept-Encoding", "identity")
	req.Header.Set(NonceHeader, nonce)
	req.GetBody = nil // never replay an inference POST after a transport failure
	response, err := h.client.Do(req)
	if err != nil {
		return 0, nil, receipt, errors.New("gateway unavailable")
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, ResponseLimit+1))
	if err != nil || len(body) > ResponseLimit {
		return 0, nil, receipt, errors.New("invalid gateway body")
	}
	media, _, _ := mime.ParseMediaType(response.Header.Get("Content-Type"))
	if media != "application/json" || (response.Header.Get("Content-Encoding") != "" && response.Header.Get("Content-Encoding") != "identity") || len(response.Header.Values(ReceiptHeader)) != 1 {
		return 0, nil, receipt, errors.New("receipt unavailable")
	}
	receipt, err = Verify(response.Header.Get(ReceiptHeader), h.cfg.Secret, nonce, response.StatusCode, body, started, time.Now())
	if err != nil {
		return 0, nil, receipt, errors.New("invalid receipt")
	}
	return response.StatusCode, body, receipt, nil
}

func Verify(header string, secret []byte, nonce string, status int, body []byte, started, now time.Time) (Receipt, error) {
	var r Receipt
	bad := errors.New("invalid enforcement receipt")
	if len(secret) != 32 || len(header) > 2048 || !digestRE.MatchString(nonce) {
		return r, bad
	}
	parts := strings.Split(header, ".")
	if len(parts) != 2 {
		return r, bad
	}
	payload, err := base64.RawURLEncoding.Strict().DecodeString(parts[0])
	if err != nil {
		return r, bad
	}
	signature, err := base64.RawURLEncoding.Strict().DecodeString(parts[1])
	if err != nil || len(signature) != 32 {
		return r, bad
	}
	mac := hmac.New(sha256.New, secret)
	_, _ = mac.Write(payload)
	if !hmac.Equal(signature, mac.Sum(nil)) {
		return r, bad
	}
	if !uniqueJSON(payload) {
		return r, bad
	}
	d := json.NewDecoder(bytes.NewReader(payload))
	d.DisallowUnknownFields()
	if d.Decode(&r) != nil {
		return r, bad
	}
	// Requiring the exact canonical payload also rejects aliases, omitted zero
	// fields and alternate encodings. The signer emits this one representation.
	canonical, err := json.Marshal(r)
	if err != nil || !bytes.Equal(payload, canonical) || r.Version != Protocol || r.PolicyID != Policy || r.Nonce != nonce || r.Status != status || r.BodySHA256 != Hash(body) || !digestRE.MatchString(r.BodySHA256) || r.IssuedAt < started.Unix()-2 || r.IssuedAt > now.Unix()+2 || now.Unix()-r.IssuedAt > 20 {
		return r, bad
	}
	switch r.Outcome {
	case "ALLOW":
		if status != 200 || !digestRE.MatchString(r.CandidateSHA256) {
			return r, bad
		}
		var parsed struct {
			Choices []struct{ Message struct{ Content string } }
		}
		if json.Unmarshal(body, &parsed) != nil || len(parsed.Choices) != 1 || Hash([]byte(parsed.Choices[0].Message.Content)) != r.CandidateSHA256 {
			return r, bad
		}
	case "REJECT":
		if status != 403 || r.CandidateSHA256 != "" {
			return r, bad
		}
	case "UNAVAILABLE":
		if status != 503 || r.CandidateSHA256 != "" {
			return r, bad
		}
	case "PROVIDER_ERROR":
		if status < 400 || status > 599 || r.CandidateSHA256 != "" {
			return r, bad
		}
	default:
		return r, bad
	}
	return r, nil
}

type request struct {
	Model    string `json:"model"`
	Messages []struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"messages"`
	Stream    bool     `json:"stream"`
	Fallbacks []string `json:"fallbacks,omitempty"`
}

func validRequest(data []byte) bool {
	if !uniqueJSON(data) {
		return false
	}
	var r request
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	if d.Decode(&r) != nil || r.Stream || len(r.Messages) != 1 || r.Model == "" || len(r.Model) > 128 || len(r.Fallbacks) > 2 || len(r.Messages[0].Content) > 32768 || (r.Messages[0].Role != "user" && r.Messages[0].Role != "system") {
		return false
	}
	for _, model := range r.Fallbacks {
		if model == "" || len(model) > 128 {
			return false
		}
	}
	// Struct matching in encoding/json is case insensitive; independently require
	// canonical request names and message fields to avoid ambiguous stream flags.
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil {
		return false
	}
	for key := range fields {
		if key != "model" && key != "messages" && key != "stream" && key != "fallbacks" {
			return false
		}
	}
	if _, ok := fields["model"]; !ok {
		return false
	}
	var messages []map[string]json.RawMessage
	if json.Unmarshal(fields["messages"], &messages) != nil || len(messages) != 1 || len(messages[0]) != 2 {
		return false
	}
	for key := range messages[0] {
		if key != "role" && key != "content" {
			return false
		}
	}
	if raw, ok := fields["stream"]; ok && string(raw) != "true" && string(raw) != "false" {
		return false
	}
	return true
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	select {
	case h.slots <- struct{}{}:
		defer func() { <-h.slots }()
	default:
		refuse(w, 503)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), h.cfg.Timeout)
	defer cancel()
	// Compare original target, not a cleaned/decoded URL. Queries, encoded paths,
	// redirects, management, alternate methods and absolute-form URLs are denied.
	if r.Method == "GET" && r.RequestURI == "/ready" {
		if !h.ready(ctx) {
			refuse(w, 503)
		} else {
			w.WriteHeader(200)
			_, _ = w.Write([]byte(`{"ready":true}`))
		}
		return
	}
	if r.Method != "POST" || r.RequestURI != Path || r.URL.RawQuery != "" {
		refuse(w, 400)
		return
	}
	media, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if len(r.Header.Values("Content-Type")) != 1 || media != "application/json" || (r.Header.Get("Content-Encoding") != "" && r.Header.Get("Content-Encoding") != "identity") || r.Header.Get("X-Bf-Async") != "" || r.Header.Get("X-Bf-Async-Id") != "" {
		refuse(w, 400)
		return
	}
	_ = http.NewResponseController(w).SetReadDeadline(time.Now().Add(2 * time.Second))
	data, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 65536))
	if err != nil {
		refuse(w, 413)
		return
	}
	_ = http.NewResponseController(w).SetReadDeadline(time.Time{})
	if !validRequest(data) {
		refuse(w, 400)
		return
	}
	status, body, receipt, err := h.exchange(ctx, data)
	if err != nil {
		refuse(w, 503)
		return
	}
	if receipt.Outcome == "REJECT" || receipt.Outcome == "UNAVAILABLE" {
		// Return plugin-owned safe refusal fields, never reflect upstream error
		// metadata on policy failures. Status/decision remain authenticated.
		policyRefusal(w, status)
		return
	}
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func refuse(w http.ResponseWriter, status int) {
	w.WriteHeader(status)
	_, _ = w.Write([]byte(`{"error":{"type":"epochguard_ingress_error","code":"epochguard_ingress_refused","message":"EpochGuard protected ingress refused the response."}}`))
}
func policyRefusal(w http.ResponseWriter, status int) {
	code, message := "epochguard_verification_unavailable", "EpochGuard verification is unavailable."
	if status == 403 {
		code, message = "epochguard_rejected", "EpochGuard refused the provider response."
	}
	body, _ := json.Marshal(map[string]any{"error": map[string]string{"type": "epochguard_policy_error", "code": code, "message": message}})
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func (h *Handler) ready(ctx context.Context) bool {
	for _, path := range []string{"/health", "/api/plugins/loaded", "/api/plugins"} {
		req, err := http.NewRequestWithContext(ctx, "GET", h.cfg.Gateway+path, nil)
		if err != nil {
			return false
		}
		req.Header.Set("X-Bifrost-Setup-Token", h.cfg.ManagementToken)
		response, err := h.client.Do(req)
		if err != nil {
			return false
		}
		data, err := io.ReadAll(io.LimitReader(response.Body, 128*1024+1))
		response.Body.Close()
		if err != nil || response.StatusCode != 200 || len(data) > 128*1024 {
			return false
		}
		if path == "/api/plugins/loaded" {
			var loaded struct{ Plugins []string }
			if json.Unmarshal(data, &loaded) != nil {
				return false
			}
			found := false
			for _, name := range loaded.Plugins {
				if name == "epochguard" {
					found = true
				}
				if name == "semantic_cache" {
					return false
				}
			}
			if !found {
				return false
			}
		}
		if path == "/api/plugins" {
			var plugins struct {
				Plugins []struct {
					Name, Placement string
					Enabled         bool
					Order           *int
					Status          struct{ Status string }
					Config          struct {
						Verifier    struct{ Mode string }
						Attestation struct{ Protocol string }
					}
				}
			}
			if json.Unmarshal(data, &plugins) != nil {
				return false
			}
			found := false
			for _, plugin := range plugins.Plugins {
				if plugin.Name == "epochguard" {
					found = plugin.Enabled && plugin.Placement == "pre_builtin" && plugin.Order != nil && *plugin.Order == 0 && plugin.Status.Status == "active" && plugin.Config.Verifier.Mode == "004b.v1" && plugin.Config.Attestation.Protocol == Protocol
				}
			}
			if !found {
				return false
			}
		}
	}
	data, _ := json.Marshal(map[string]any{"model": "fixture/epochguard-test", "messages": []map[string]string{{"role": "user", "content": h.cfg.ProbeCandidate}}, "stream": false})
	status, _, receipt, err := h.exchange(ctx, data)
	return err == nil && status == 200 && receipt.Outcome == "ALLOW"
}

func uniqueJSON(data []byte) bool {
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
				for i := 0; d.More(); i++ {
					if i >= 64 || !walk(depth+1) {
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
