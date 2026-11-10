package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

const verificationSchema = "003a.v1"
const verificationPolicy = "python-windows-latest-v1"
const primaryURL = "https://www.python.org/downloads/windows/"
const versionPattern = `3\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]{0,2})`

var claimPattern = regexp.MustCompile(`^The latest stable Python 3 release for Windows listed on Python\.org is (` + versionPattern + `)\.$`)
var versionRE = regexp.MustCompile(`^` + versionPattern + `$`)
var digestRE = regexp.MustCompile(`^[0-9a-f]{64}$`)
var retrievalIDRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)

type HTTPVerificationConfig struct {
	URL          string `json:"url"`
	TimeoutMS    int    `json:"timeout_ms"`
	EvidenceMode string `json:"evidence_mode"`
}

type verificationRequest struct {
	SchemaVersion   string `json:"schema_version"`
	PolicyID        string `json:"policy_id"`
	RequestID       string `json:"request_id"`
	Candidate       string `json:"candidate"`
	CandidateSHA256 string `json:"candidate_sha256"`
}

type verificationClaim struct {
	Kind    string `json:"kind"`
	Version string `json:"version"`
}

type verificationEvidence struct {
	URL             string    `json:"url"`
	RetrievalMode   string    `json:"retrieval_mode"`
	ContentSHA256   string    `json:"content_sha256"`
	RetrievedAt     time.Time `json:"retrieved_at"`
	ObservedAt      time.Time `json:"observed_at"`
	RetrievalID     string    `json:"retrieval_id"`
	ObservedVersion string    `json:"observed_version"`
	Excerpt         string    `json:"excerpt"`
}

type verificationResponse struct {
	SchemaVersion   string                 `json:"schema_version"`
	PolicyID        string                 `json:"policy_id"`
	RequestID       string                 `json:"request_id"`
	CandidateSHA256 string                 `json:"candidate_sha256"`
	Claim           *verificationClaim     `json:"claim"`
	Verdict         string                 `json:"verdict"`
	ReasonCode      string                 `json:"reason_code"`
	Evidence        []verificationEvidence `json:"evidence"`
	CheckedAt       time.Time              `json:"checked_at"`
}

type httpDecisionSource struct {
	endpoint     string
	client       *http.Client
	evidenceMode string
}

func newHTTPDecisionSource(config HTTPVerificationConfig) (*httpDecisionSource, error) {
	if config.EvidenceMode == "" {
		config.EvidenceMode = "tavily_live"
	}
	if config.EvidenceMode != "tavily_live" && config.EvidenceMode != "fixture" {
		return nil, errors.New("epochguard: unknown evidence mode")
	}
	u, err := url.Parse(config.URL)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Path != "/v1/verify" {
		return nil, errors.New("epochguard: invalid trusted verifier URL")
	}
	if config.TimeoutMS == 0 {
		config.TimeoutMS = 6000
	}
	if config.TimeoutMS < 100 || config.TimeoutMS > 30000 {
		return nil, errors.New("epochguard: verifier timeout must be 100..30000ms")
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	transport.DisableCompression = true
	transport.MaxConnsPerHost = 16
	transport.MaxIdleConnsPerHost = 8
	transport.IdleConnTimeout = 30 * time.Second
	return &httpDecisionSource{endpoint: config.URL, evidenceMode: config.EvidenceMode, client: &http.Client{
		Transport: transport, Timeout: time.Duration(config.TimeoutMS) * time.Millisecond,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}}, nil
}

// Only one complete plain assistant message is covered by this policy. Reject
// tools, reasoning, multimodal content, extra choices and partial completions.
// All fields below were inspected in the exact core v1.14.1 response schema.
func plainCandidate(resp *schemas.BifrostResponse) (string, string, error) {
	bad := errors.New("epochguard: unsupported provider candidate")
	if resp == nil || resp.ChatResponse == nil {
		return "", "", bad
	}
	chat := resp.ChatResponse
	if chat.Object != "chat.completion" || len(chat.Choices) != 1 || len(chat.SearchResults) > 0 || len(chat.Videos) > 0 || len(chat.Citations) > 0 {
		return "", "", bad
	}
	choice := chat.Choices[0]
	if choice.ChatNonStreamResponseChoice == nil || choice.TextCompletionResponseChoice != nil || choice.ChatStreamResponseChoice != nil || choice.FinishReason == nil || *choice.FinishReason != "stop" || choice.LogProbs != nil {
		return "", "", bad
	}
	msg := choice.Message
	if msg == nil || msg.Role != schemas.ChatMessageRoleAssistant || msg.ChatAssistantMessage != nil || msg.ChatToolMessage != nil || msg.Name != nil || msg.Content == nil || msg.Content.ContentStr == nil || msg.Content.ContentBlocks != nil {
		return "", "", bad
	}
	text := *msg.Content.ContentStr
	if len(text) > 512 {
		return "", "", bad
	}
	match := claimPattern.FindStringSubmatch(text)
	if match == nil {
		return "", "", bad
	}
	return text, match[1], nil
}

func (s *httpDecisionSource) Decide(ctx context.Context, resp *schemas.BifrostResponse) (Decision, error) {
	started := time.Now()
	text, version, err := plainCandidate(resp)
	if err != nil {
		return Unavailable, verificationFailure{category: "unsupported_candidate"}
	}
	sum := sha256.Sum256([]byte(text))
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return Unavailable, verificationFailure{category: "verification_unavailable"}
	}
	payload := verificationRequest{verificationSchema, verificationPolicy, hex.EncodeToString(nonce), text, hex.EncodeToString(sum[:])}
	body, err := json.Marshal(payload)
	if err != nil {
		return Unavailable, verificationFailure{category: "request_failure"}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.endpoint, bytes.NewReader(body))
	if err != nil {
		return Unavailable, verificationFailure{category: "request_failure"}
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := s.client.Do(req)
	if err != nil {
		return Unavailable, transportFailure(err)
	}
	defer response.Body.Close()
	media, _, _ := mime.ParseMediaType(response.Header.Get("Content-Type"))
	if response.StatusCode != http.StatusOK {
		return Unavailable, verificationFailure{category: "verifier_http_failure", status: response.StatusCode}
	}
	if media != "application/json" {
		return Unavailable, verificationFailure{category: "invalid_contract", status: response.StatusCode}
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 32769))
	if err != nil {
		failure := transportFailure(err)
		failure.status = response.StatusCode
		return Unavailable, failure
	}
	if len(data) > 32768 {
		return Unavailable, verificationFailure{category: "invalid_contract", status: response.StatusCode}
	}
	var verdict verificationResponse
	if err := strictJSON(data, &verdict); err != nil {
		return Unavailable, verificationFailure{category: "invalid_contract", status: response.StatusCode}
	}
	decision, err := validateVerification(payload, version, verdict, started, time.Now())
	if decision != Unavailable && (len(verdict.Evidence) != 1 || verdict.Evidence[0].RetrievalMode != s.evidenceMode) {
		return Unavailable, verificationFailure{category: "invalid_contract", status: response.StatusCode}
	}
	if err != nil {
		return Unavailable, verificationFailure{category: "invalid_contract", status: response.StatusCode}
	}
	// Validation above restricts verdict/reason to fixed contract literals.
	safeLogf("epochguard verification_verdict=%s reason=%s latency_ms=%d", verdict.Verdict, verdict.ReasonCode, time.Since(started).Milliseconds())
	return decision, err
}

func validateVerification(request verificationRequest, version string, v verificationResponse, started, now time.Time) (Decision, error) {
	bad := errors.New("epochguard: invalid verification record")
	if v.SchemaVersion != verificationSchema || v.PolicyID != verificationPolicy || v.RequestID != request.RequestID || v.CandidateSHA256 != request.CandidateSHA256 || v.CheckedAt.Before(started.Add(-2*time.Second)) || v.CheckedAt.After(now.Add(2*time.Second)) {
		return Unavailable, bad
	}
	if v.Verdict == "INSUFFICIENT" {
		switch v.ReasonCode {
		case "CLAIM_AHEAD_OF_SOURCE", "UNSUPPORTED_CLAIM", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_EVIDENCE", "RETRIEVAL_TIMEOUT", "RETRIEVAL_FAILURE", "VERIFIER_ERROR", "STALE_OBSERVATION":
			return Unavailable, nil
		default:
			return Unavailable, bad
		}
	}
	if v.Claim == nil || v.Claim.Kind != "python_windows_latest_stable" || v.Claim.Version != version || len(v.Evidence) != 1 {
		return Unavailable, bad
	}
	e := v.Evidence[0]
	if e.URL != primaryURL || !digestRE.MatchString(e.ContentSHA256) || !retrievalIDRE.MatchString(e.RetrievalID) || !versionRE.MatchString(e.ObservedVersion) || e.Excerpt != "Latest Python 3 Release - Python "+e.ObservedVersion {
		return Unavailable, bad
	}
	if !e.RetrievedAt.Equal(e.ObservedAt) || e.ObservedAt.Before(started.Add(-2*time.Second)) || e.ObservedAt.After(v.CheckedAt) || e.ObservedAt.After(now.Add(2*time.Second)) || now.Sub(e.ObservedAt) > 60*time.Second {
		return Unavailable, bad
	}
	if v.Verdict == "SUPPORTED" && v.ReasonCode == "MATCHED_PRIMARY_LABEL" && version == e.ObservedVersion {
		return Allow, nil
	}
	if v.Verdict == "CONTRADICTED" && v.ReasonCode == "OLDER_THAN_PRIMARY_LABEL" && compareVersion(version, e.ObservedVersion) < 0 {
		return Reject, nil
	}
	return Unavailable, bad
}

func compareVersion(a, b string) int {
	left, right := strings.Split(a, "."), strings.Split(b, ".")
	for i := range 3 {
		x, _ := strconv.Atoi(left[i])
		y, _ := strconv.Atoi(right[i])
		if x < y {
			return -1
		}
		if x > y {
			return 1
		}
	}
	return 0
}

// This fixed contract accepts only exact canonical names, at their own object
// level. Reject aliases (including Unicode folds), unknown and duplicate names
// before typed decoding can apply encoding/json's case-insensitive matching.
func strictJSON(data []byte, target *verificationResponse) error {
	tokens := json.NewDecoder(bytes.NewReader(data))
	var walk func(string, int) error
	walk = func(object string, depth int) error {
		if depth > 4 {
			return errors.New("invalid contract nesting")
		}
		t, err := tokens.Token()
		if err != nil {
			return err
		}
		if d, ok := t.(json.Delim); ok {
			switch d {
			case '{':
				keys := map[string]bool{}
				for tokens.More() {
					key, err := tokens.Token()
					if err != nil {
						return err
					}
					name, ok := key.(string)
					if !ok || keys[name] {
						return errors.New("duplicate key")
					}
					child, allowed := contractField(object, name)
					if !allowed {
						return errors.New("noncanonical contract field")
					}
					keys[name] = true
					if err := walk(child, depth+1); err != nil {
						return err
					}
				}
			case '[':
				for tokens.More() {
					if err := walk(object, depth+1); err != nil {
						return err
					}
				}
			default:
				return errors.New("invalid delimiter")
			}
			_, err = tokens.Token()
			return err
		}
		return nil
	}
	if err := walk("response", 0); err != nil {
		return err
	}
	if _, err := tokens.Token(); err != io.EOF {
		return errors.New("trailing JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func contractField(object, name string) (string, bool) {
	switch object {
	case "response":
		switch name {
		case "schema_version", "policy_id", "request_id", "candidate_sha256", "verdict", "reason_code", "checked_at":
			return "scalar", true
		case "claim":
			return "claim", true
		case "evidence":
			return "evidence", true
		}
	case "claim":
		switch name {
		case "kind", "version":
			return "scalar", true
		}
	case "evidence":
		switch name {
		case "url", "retrieval_mode", "content_sha256", "retrieved_at", "observed_at", "retrieval_id", "observed_version", "excerpt":
			return "scalar", true
		}
	}
	return "", false
}
