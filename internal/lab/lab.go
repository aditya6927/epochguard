// Package lab is a local presentation boundary, never a verification authority.
package lab

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"strings"
	"time"
	"unicode/utf8"
)

const Origin = "http://127.0.0.1:8787"
const chatPath = "/openai/v1/chat/completions"
const Supported = "Python.org currently lists Python 3.15.2 as its latest stable Windows release.\nPyPI reports requests version 2.34.2."

type Config struct {
	Ingress, Unsafe string
	Assets          fs.FS
	Timeout         time.Duration
	MaxActive       int
}

type Handler struct {
	cfg    Config
	client *http.Client
	slots  chan struct{}
}

type Scenario struct {
	ID             string `json:"id"`
	Label          string `json:"label"`
	Description    string `json:"description"`
	Candidate      string `json:"candidate"`
	ExpectedStatus int    `json:"expected_status"`
}

func Scenarios() []Scenario {
	return []Scenario{
		{"supported", "Supported claims", "Both versions match the simulated observations.", Supported, 200},
		{"contradicted", "Older Python", "An older Python claim beside a supported requests claim.", strings.Replace(Supported, "3.15.2", "3.15.1", 1), 403},
		{"unsupported", "Extra assertion", "An additional assertion falls outside the bounded language.", Supported + "\nPython is the safest programming language.", 503},
		{"missing-plugin", "Missing plugin", "A fixed no-plugin gateway behind a protected ingress.", Supported, 503},
		{"provider-error", "Provider failure", "The fixture returns a genuine upstream failure before verification.", Supported, 400},
	}
}

func New(cfg Config) (*Handler, error) {
	for _, target := range []string{cfg.Ingress, cfg.Unsafe} {
		u, err := url.Parse(target)
		if err != nil || u.Scheme != "http" || u.Host == "" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
			return nil, errors.New("invalid trusted ingress configuration")
		}
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = 10 * time.Second
	}
	if cfg.MaxActive == 0 {
		cfg.MaxActive = 4
	}
	if cfg.Timeout < time.Millisecond || cfg.Timeout > 10*time.Second || cfg.MaxActive < 1 || cfg.MaxActive > 4 || cfg.Assets == nil {
		return nil, errors.New("invalid lab bounds")
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.Proxy = nil
	transport.DisableCompression = true
	transport.MaxConnsPerHost = cfg.MaxActive
	transport.MaxIdleConnsPerHost = cfg.MaxActive
	transport.MaxResponseHeaderBytes = 16 * 1024
	return &Handler{cfg: cfg, slots: make(chan struct{}, cfg.MaxActive), client: &http.Client{
		Transport: transport, Timeout: cfg.Timeout,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}}, nil
}

func (h *Handler) Close() { h.client.CloseIdleConnections() }

type Result struct {
	Status         int     `json:"status"`
	UpstreamStatus *int    `json:"upstream_status"`
	Outcome        string  `json:"outcome"`
	Boundary       string  `json:"boundary"`
	Content        *string `json:"content"`
	Error          *string `json:"error"`
	ExactMatch     bool    `json:"exact_content_match"`
	EvidenceMode   string  `json:"evidence_mode"`
}

func emit(w http.ResponseWriter, result Result) {
	result.EvidenceMode = "fixture"
	w.WriteHeader(result.Status)
	_ = json.NewEncoder(w).Encode(result)
}

func unavailable(w http.ResponseWriter, status int, boundary, message string, upstream *int) {
	emit(w, Result{Status: status, UpstreamStatus: upstream, Outcome: "UNAVAILABLE", Boundary: boundary, Error: &message})
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
	w.Header().Set("Content-Type", "application/json")
	// Cross-site links may navigate to the UI, but cannot read APIs, embed the
	// page, or dispatch verification. API origin checks below remain mandatory.
	navigation := r.Method == "GET" && r.RequestURI == "/" && r.Header.Get("Sec-Fetch-Mode") == "navigate" && r.Header.Get("Sec-Fetch-Dest") == "document"
	if r.Host != "127.0.0.1:8787" || (r.Header.Get("Origin") != "" && r.Header.Get("Origin") != Origin) || (!navigation && r.Header.Get("Sec-Fetch-Site") != "" && r.Header.Get("Sec-Fetch-Site") != "same-origin" && r.Header.Get("Sec-Fetch-Site") != "none") {
		unavailable(w, 403, "lab", "This local Lab accepts same-origin requests only.", nil)
		return
	}
	if r.Method == "GET" && r.RequestURI == "/healthz" {
		_, _ = io.WriteString(w, `{"ready":true}`)
		return
	}
	if r.Method == "GET" && r.RequestURI == "/api/demo/info" {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"evidence_mode": "fixture", "receipt_protocol": "004g.receipt.v2", "scenarios": Scenarios(),
			"candidate_limit": map[string]int{"code_points": 8192, "utf8_bytes": 32768},
			"policies": []map[string]string{
				{"id": "python-windows-latest-v1", "label": "Python.org / Windows", "fixture_version": "3.15.2", "source": "https://www.python.org/downloads/windows/"},
				{"id": "pypi-requests-reported-v1", "label": "PyPI / requests", "fixture_version": "2.34.2", "source": "https://pypi.org/pypi/requests/json"},
			},
			"live_qualification": "Narrow real-source acceptance reviewed and met on November 15, 2026; controlled provider, not a commercial model or production qualification.",
		})
		return
	}
	if r.Method == "POST" && r.RequestURI == "/api/demo/verify" {
		h.verify(w, r)
		return
	}
	if r.Method == "GET" && (r.RequestURI == "/" || strings.HasPrefix(r.RequestURI, "/assets/")) && !strings.ContainsAny(r.RequestURI, "%?\\") {
		name := strings.TrimPrefix(r.URL.Path, "/")
		if name == "" {
			name = "index.html"
		}
		if fs.ValidPath(name) {
			data, err := fs.ReadFile(h.cfg.Assets, name)
			if err == nil {
				switch {
				case strings.HasSuffix(name, ".js"):
					w.Header().Set("Content-Type", "text/javascript; charset=utf-8")
				case strings.HasSuffix(name, ".css"):
					w.Header().Set("Content-Type", "text/css; charset=utf-8")
				case name == "index.html":
					w.Header().Set("Content-Type", "text/html; charset=utf-8")
				default:
					w.Header().Set("Content-Type", "application/octet-stream")
				}
				_, _ = w.Write(data)
				return
			}
		}
	}
	unavailable(w, 404, "lab", "Unknown Lab route.", nil)
}

func input(data []byte) (string, string, error) {
	if !utf8.Valid(data) {
		return "", "", errors.New("invalid encoding")
	}
	d := json.NewDecoder(bytes.NewReader(data))
	token, err := d.Token()
	if err != nil || token != json.Delim('{') {
		return "", "", errors.New("invalid object")
	}
	fields := map[string]string{}
	for d.More() {
		token, err = d.Token()
		key, ok := token.(string)
		if err != nil || !ok || (key != "scenario" && key != "candidate") {
			return "", "", errors.New("unknown field")
		}
		if _, exists := fields[key]; exists {
			return "", "", errors.New("duplicate field")
		}
		var value string
		if err = d.Decode(&value); err != nil {
			return "", "", err
		}
		fields[key] = value
	}
	if _, err = d.Token(); err != nil {
		return "", "", err
	}
	if _, err = d.Token(); err != io.EOF || len(fields) != 2 {
		return "", "", errors.New("invalid fields")
	}
	text := fields["candidate"]
	if text == "" || len(text) > 32768 || utf8.RuneCountInString(text) > 8192 || strings.ContainsRune(text, utf8.RuneError) {
		return "", "", errors.New("invalid candidate bounds")
	}
	for _, c := range text {
		if c < 32 && c != '\t' && c != '\r' && c != '\n' || c == 127 {
			return "", "", errors.New("invalid control")
		}
	}
	return fields["scenario"], text, nil
}

func (h *Handler) verify(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Origin") != Origin || r.Header.Get("X-EpochGuard-Lab") != "1" || r.Header.Get("Content-Type") != "application/json" || len(r.Header.Values("Content-Type")) != 1 || (r.Header.Get("Content-Encoding") != "" && r.Header.Get("Content-Encoding") != "identity") {
		unavailable(w, 400, "lab", "Use the Lab's JSON request format.", nil)
		return
	}
	select {
	case h.slots <- struct{}{}:
		defer func() { <-h.slots }()
	default:
		unavailable(w, 503, "lab", "The Lab is busy. Wait for the current requests to finish.", nil)
		return
	}
	data, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 65536))
	if err != nil {
		unavailable(w, 413, "lab", "The request exceeds the Lab input limit.", nil)
		return
	}
	scenario, candidate, err := input(data)
	if err != nil {
		unavailable(w, 400, "lab", "Enter a valid bounded candidate and known scenario.", nil)
		return
	}
	target, role := h.cfg.Ingress, "user"
	known := scenario == "custom"
	for _, entry := range Scenarios() {
		known = known || entry.ID == scenario
	}
	if !known {
		unavailable(w, 400, "lab", "Unknown Lab scenario.", nil)
		return
	}
	if scenario == "missing-plugin" {
		target = h.cfg.Unsafe
	}
	if scenario == "provider-error" {
		role = "system"
	}
	// Exact submitted content, fixed provider/model/message shape. No browser
	// header, URL, policy, fault control, fallback or stream option is forwarded.
	request, _ := json.Marshal(map[string]any{"model": "fixture/epochguard-test", "messages": []map[string]string{{"role": role, "content": candidate}}, "stream": false})
	ctx, cancel := context.WithTimeout(r.Context(), h.cfg.Timeout)
	defer cancel()
	upstream, _ := http.NewRequestWithContext(ctx, "POST", target+chatPath, bytes.NewReader(request))
	upstream.GetBody = nil
	upstream.Header.Set("Content-Type", "application/json")
	upstream.Header.Set("Accept-Encoding", "identity")
	response, err := h.client.Do(upstream)
	if err != nil {
		unavailable(w, 503, "infrastructure", "The protected response is unavailable. No answer was released.", nil)
		return
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 256*1024+1))
	if err != nil || len(body) > 256*1024 || response.Header.Get("Content-Type") != "application/json" || (response.Header.Get("Content-Encoding") != "" && response.Header.Get("Content-Encoding") != "identity") {
		unavailable(w, 503, "infrastructure", "The protected response could not be safely displayed.", &response.StatusCode)
		return
	}
	result, err := project(body, response.StatusCode, candidate)
	if err != nil {
		unavailable(w, 503, "infrastructure", "The protected response could not be safely displayed.", &response.StatusCode)
		return
	}
	emit(w, result)
}

func project(body []byte, status int, candidate string) (Result, error) {
	// Equality against fixed canonical shapes rejects metadata, unknown/duplicate
	// keys and alternate error text; no untrusted error string reaches the UI.
	var object any
	if !utf8.Valid(body) || !uniqueJSON(body) || json.Unmarshal(body, &object) != nil {
		return Result{}, errors.New("invalid response")
	}
	canonical, _ := json.Marshal(object)
	result := Result{Status: status, UpstreamStatus: &status, Boundary: "protected_ingress"}
	if status == 200 {
		expected, _ := json.Marshal(map[string]any{"object": "chat.completion", "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": candidate}}}})
		if bytes.Equal(canonical, expected) {
			result.Content, result.ExactMatch, result.Outcome = &candidate, true, "ALLOW"
			return result, nil
		}
	}
	errorsAllowed := []struct {
		status                                 int
		kind, code, message, outcome, boundary string
	}{
		{403, "epochguard_policy_error", "epochguard_rejected", "EpochGuard refused the provider response.", "REJECT", "policy"},
		{503, "epochguard_policy_error", "epochguard_verification_unavailable", "EpochGuard verification is unavailable.", "UNAVAILABLE", "policy"},
		{503, "epochguard_ingress_error", "epochguard_ingress_refused", "EpochGuard protected ingress refused the response.", "INGRESS_REFUSED", "ingress"},
	}
	for _, kind := range []string{"invalid_request_error", "authentication_error", "permission_error", "rate_limit_error", "server_error", "provider_error"} {
		errorsAllowed = append(errorsAllowed, struct {
			status                                 int
			kind, code, message, outcome, boundary string
		}{status, kind, "epochguard_provider_error", "Provider request failed.", "PROVIDER_ERROR", "provider"})
	}
	for _, allowed := range errorsAllowed {
		if status != allowed.status || status < 400 || status > 599 {
			continue
		}
		expected, _ := json.Marshal(map[string]any{"error": map[string]string{"type": allowed.kind, "code": allowed.code, "message": allowed.message}})
		if bytes.Equal(canonical, expected) {
			result.Error, result.Outcome, result.Boundary = &allowed.message, allowed.outcome, allowed.boundary
			return result, nil
		}
	}
	return Result{}, errors.New("unexpected protected response")
}

func uniqueJSON(data []byte) bool {
	d := json.NewDecoder(bytes.NewReader(data))
	var value func(int) bool
	value = func(depth int) bool {
		if depth > 12 {
			return false
		}
		token, err := d.Token()
		if err != nil {
			return false
		}
		if delim, ok := token.(json.Delim); ok {
			seen := map[string]bool{}
			for d.More() {
				if delim == '{' {
					key, err := d.Token()
					name, ok := key.(string)
					if err != nil || !ok || seen[name] {
						return false
					}
					seen[name] = true
				}
				if !value(depth + 1) {
					return false
				}
			}
			_, err = d.Token()
			return err == nil
		}
		return true
	}
	if !value(0) {
		return false
	}
	_, err := d.Token()
	return err == io.EOF
}
