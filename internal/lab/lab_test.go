package lab

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"testing/fstest"
	"time"
)

func allowed(text string) []byte {
	data, _ := json.Marshal(map[string]any{"object": "chat.completion", "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": text}}}})
	return data
}

func requestJSON(scenario, text string) string {
	data, _ := json.Marshal(map[string]string{"scenario": scenario, "candidate": text})
	return string(data)
}

func call(h http.Handler, body string) *httptest.ResponseRecorder {
	r := httptest.NewRequest("POST", Origin+"/api/demo/verify", strings.NewReader(body))
	r.RequestURI = "/api/demo/verify"
	r.Header.Set("Origin", Origin)
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-EpochGuard-Lab", "1")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func handler(t *testing.T, upstream http.HandlerFunc, timeout time.Duration, slots int) *Handler {
	t.Helper()
	s := httptest.NewServer(upstream)
	t.Cleanup(s.Close)
	h, err := New(Config{Ingress: s.URL, Unsafe: s.URL, Assets: fstest.MapFS{"index.html": {Data: []byte("fixture static page")}}, Timeout: timeout, MaxActive: slots})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(h.Close)
	return h
}

func TestCrossSiteNavigationDoesNotOpenAPIs(t *testing.T) {
	h := handler(t, func(w http.ResponseWriter, r *http.Request) { t.Fatal("navigation dispatched upstream") }, time.Second, 4)
	for _, tc := range []struct {
		method, path, mode, dest, origin, host string
		status                                 int
	}{
		{"GET", "/", "navigate", "document", "", "127.0.0.1:8787", 200},
		{"GET", "/", "navigate", "iframe", "", "127.0.0.1:8787", 403},
		{"GET", "/", "cors", "document", "", "127.0.0.1:8787", 403},
		{"GET", "/", "navigate", "document", "http://attacker.invalid", "127.0.0.1:8787", 403},
		{"GET", "/", "navigate", "document", "", "attacker.invalid", 403},
		{"GET", "/api/demo/info", "navigate", "document", "", "127.0.0.1:8787", 403},
		{"GET", "/assets/test.js", "navigate", "document", "", "127.0.0.1:8787", 403},
		{"POST", "/api/demo/verify", "navigate", "document", "", "127.0.0.1:8787", 403},
		{"GET", "/?candidate=x", "navigate", "document", "", "127.0.0.1:8787", 403},
	} {
		r := httptest.NewRequest(tc.method, "http://127.0.0.1:8787"+tc.path, nil)
		r.RequestURI = tc.path
		r.Host = tc.host
		r.Header.Set("Sec-Fetch-Site", "cross-site")
		r.Header.Set("Sec-Fetch-Mode", tc.mode)
		r.Header.Set("Sec-Fetch-Dest", tc.dest)
		r.Header.Set("Origin", tc.origin)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != tc.status || w.Header().Get("Access-Control-Allow-Origin") != "" {
			t.Fatalf("%s %s: %d", tc.method, tc.path, w.Code)
		}
	}
}

func TestSubmittedBytesFixedRequestAndNoBrowserHeaders(t *testing.T) {
	text := "\t" + Supported + "\r\n\t"
	h := handler(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.RequestURI != chatPath || r.Header.Get("Authorization") != "" || r.Header.Get("Cookie") != "" || r.Header.Get("X-EpochGuard-Internal-Receipt") != "" || r.Header.Get("Origin") != "" {
			t.Error("unexpected forwarded route or client header")
		}
		var value map[string]json.RawMessage
		if json.NewDecoder(r.Body).Decode(&value) != nil || len(value) != 3 || string(value["model"]) != `"fixture/epochguard-test"` || string(value["stream"]) != "false" {
			t.Error("unexpected provider request")
		}
		var messages []map[string]string
		_ = json.Unmarshal(value["messages"], &messages)
		if len(messages) != 1 || messages[0]["content"] != text || messages[0]["role"] != "user" {
			t.Error("candidate was replaced or normalized")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Provider-Text", "PRIVATE_PROVIDER_METADATA")
		w.Header().Set("X-EpochGuard-Internal-Receipt", "PRIVATE_RECEIPT")
		_, _ = w.Write(allowed(text))
	}, 0, 0)
	r := httptest.NewRequest("POST", Origin+"/api/demo/verify", strings.NewReader(requestJSON("custom", text)))
	r.RequestURI = "/api/demo/verify"
	for k, v := range map[string]string{"Origin": Origin, "Content-Type": "application/json", "X-EpochGuard-Lab": "1", "Authorization": "PRIVATE_AUTH", "Cookie": "PRIVATE_COOKIE", "X-EpochGuard-Internal-Receipt": "PRIVATE_RECEIPT"} {
		r.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	var result Result
	_ = json.Unmarshal(w.Body.Bytes(), &result)
	if w.Code != 200 || result.Content == nil || *result.Content != text || !result.ExactMatch || result.Outcome != "ALLOW" {
		t.Fatalf("unexpected safe outcome: %d", w.Code)
	}
	if strings.Contains(w.Body.String(), "PRIVATE_") || w.Header().Get("X-Provider-Text") != "" || w.Header().Get("X-EpochGuard-Internal-Receipt") != "" || w.Header().Get("Cache-Control") != "no-store" {
		t.Fatal("upstream headers leaked")
	}
}

func TestValidationNeverDispatchesUntrustedInput(t *testing.T) {
	h := handler(t, func(w http.ResponseWriter, r *http.Request) { t.Error("invalid input reached ingress") }, 0, 0)
	for _, value := range []string{`{`, `[]`, `{"candidate":"x"}`, `{"scenario":"custom","candidate":null}`,
		`{"scenario":"custom","candidate":"x","url":"http://untrusted.invalid"}`, `{"scenario":"custom","candidate":"x","candidate":"y"}`,
		`{"Scenario":"custom","candidate":"x"}`, `{"scenario":"custom","candidate":"\ud800"}`, `{"scenario":"custom","candidate":"\u0000"}`,
		`{"scenario":"http://untrusted.invalid","candidate":"x"}`, requestJSON("custom", strings.Repeat("x", 8193)),
		requestJSON("custom", strings.Repeat("x", 65536)), requestJSON("custom", "x") + `{}`, "{\"scenario\":\"custom\",\"candidate\":\"\xff\"}"} {
		t.Run(value[:min(35, len(value))], func(t *testing.T) {
			w := call(h, value)
			if w.Code != 400 && w.Code != 413 {
				t.Fatalf("unexpected validation status %d", w.Code)
			}
			if strings.Contains(w.Body.String(), "untrusted.invalid") {
				t.Fatal("input reflected")
			}
		})
	}
}

func TestOriginHostAndRouteRestrictions(t *testing.T) {
	h := handler(t, func(w http.ResponseWriter, r *http.Request) { t.Error("untrusted request dispatched") }, 0, 0)
	for _, change := range []string{"host", "origin", "no-origin", "fetch-site", "no-header", "content-type", "encoding", "management", "proxy", "query", "encoded", "put"} {
		t.Run(change, func(t *testing.T) {
			r := httptest.NewRequest("POST", Origin+"/api/demo/verify", strings.NewReader(requestJSON("custom", "x")))
			r.RequestURI = "/api/demo/verify"
			r.Header.Set("Origin", Origin)
			r.Header.Set("X-EpochGuard-Lab", "1")
			r.Header.Set("Content-Type", "application/json")
			switch change {
			case "host":
				r.Host = "attacker.invalid:8787"
			case "origin":
				r.Header.Set("Origin", "http://attacker.invalid")
			case "no-origin":
				r.Header.Del("Origin")
			case "fetch-site":
				r.Header.Set("Sec-Fetch-Site", "cross-site")
			case "no-header":
				r.Header.Del("X-EpochGuard-Lab")
			case "content-type":
				r.Header.Set("Content-Type", "text/plain")
			case "encoding":
				r.Header.Set("Content-Encoding", "gzip")
			case "management":
				r.RequestURI = "/api/plugins"
			case "proxy":
				r.RequestURI = "/api/proxy?url=http://gateway:8080"
			case "query":
				r.RequestURI += "?url=http://untrusted.invalid"
			case "encoded":
				r.RequestURI = "/api/demo/%76erify"
			case "put":
				r.Method = "PUT"
			}
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code < 400 || strings.Contains(w.Body.String(), "attacker") || w.Header().Get("Access-Control-Allow-Origin") != "" {
				t.Fatal("request restriction failed")
			}
		})
	}
}

func TestOnlyTwoTrustedTargetsAndFixedFailureRole(t *testing.T) {
	for _, id := range []string{"custom", "supported", "contradicted", "unsupported", "provider-error", "missing-plugin"} {
		t.Run(id, func(t *testing.T) {
			var unsafeCalls atomic.Int32
			unsafe := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				unsafeCalls.Add(1)
				w.Header().Set("Content-Type", "application/json")
				_, _ = io.WriteString(w, `{"error":{"type":"epochguard_ingress_error","code":"epochguard_ingress_refused","message":"EpochGuard protected ingress refused the response."}}`)
			}))
			defer unsafe.Close()
			h := handler(t, func(w http.ResponseWriter, r *http.Request) {
				var value struct {
					Messages []struct{ Role, Content string }
				}
				_ = json.NewDecoder(r.Body).Decode(&value)
				role := "user"
				if id == "provider-error" {
					role = "system"
				}
				if value.Messages[0].Role != role || value.Messages[0].Content != "submitted candidate" {
					t.Error("scenario rewrote input")
				}
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write(allowed("submitted candidate"))
			}, 0, 0)
			h.cfg.Unsafe = unsafe.URL
			call(h, requestJSON(id, "submitted candidate"))
			if (id == "missing-plugin") != (unsafeCalls.Load() == 1) {
				t.Fatal("wrong trusted target")
			}
		})
	}
}

func TestStrictResponseProjection(t *testing.T) {
	for _, value := range []struct {
		status  int
		body    string
		outcome string
	}{
		{403, `{"error":{"type":"epochguard_policy_error","code":"epochguard_rejected","message":"EpochGuard refused the provider response."}}`, "REJECT"},
		{503, `{"error":{"type":"epochguard_policy_error","code":"epochguard_verification_unavailable","message":"EpochGuard verification is unavailable."}}`, "UNAVAILABLE"},
		{503, `{"error":{"type":"epochguard_ingress_error","code":"epochguard_ingress_refused","message":"EpochGuard protected ingress refused the response."}}`, "INGRESS_REFUSED"},
		{400, `{"error":{"type":"invalid_request_error","code":"epochguard_provider_error","message":"Provider request failed."}}`, "PROVIDER_ERROR"},
		{200, `{"object":"chat.completion","choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"x"}}],"id":"PRIVATE_METADATA"}`, ""},
		{200, `{"object":"chat.completion","choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"x","content":"x"}}]}`, ""},
		{503, `{"error":{"type":"epochguard_policy_error","code":"epochguard_verification_unavailable","message":"PRIVATE_PROVIDER_CANDIDATE"}}`, ""},
		{400, `{"error":{"message":"PRIVATE_PROVIDER_TEXT"}}`, ""},
		{302, `{}`, ""},
	} {
		result, err := project([]byte(value.body), value.status, "x")
		if value.outcome == "" {
			if err == nil {
				t.Fatal("unsafe response accepted")
			}
		} else if err != nil || result.Outcome != value.outcome || result.Content != nil {
			t.Fatal("safe outcome lost")
		}
	}
}

func TestTimeoutOversizeRedirectAndRecovery(t *testing.T) {
	for _, fault := range []string{"timeout", "oversize", "redirect", "wrong-type"} {
		t.Run(fault, func(t *testing.T) {
			var mu sync.Mutex
			fail := true
			h := handler(t, func(w http.ResponseWriter, r *http.Request) {
				mu.Lock()
				current := fail
				mu.Unlock()
				w.Header().Set("Content-Type", "application/json")
				if current {
					switch fault {
					case "timeout":
						time.Sleep(70 * time.Millisecond)
					case "oversize":
						_, _ = io.WriteString(w, strings.Repeat("PRIVATE_TEXT", 30000))
						return
					case "redirect":
						http.Redirect(w, r, "http://untrusted.invalid", 302)
						return
					case "wrong-type":
						w.Header().Set("Content-Type", "text/plain")
					}
				}
				_, _ = w.Write(allowed("x"))
			}, 30*time.Millisecond, 0)
			w := call(h, requestJSON("custom", "x"))
			if w.Code != 503 || strings.Contains(w.Body.String(), "PRIVATE_TEXT") {
				t.Fatal("unsafe upstream failure")
			}
			mu.Lock()
			fail = false
			mu.Unlock()
			if call(h, requestJSON("custom", "x")).Code != 200 {
				t.Fatal("failed recovery")
			}
		})
	}
}

func TestImmediateAdmissionNoQueue(t *testing.T) {
	entered, release := make(chan struct{}), make(chan struct{})
	h := handler(t, func(w http.ResponseWriter, r *http.Request) {
		close(entered)
		<-release
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(allowed("x"))
	}, 0, 1)
	done := make(chan struct{})
	go func() { defer close(done); call(h, requestJSON("custom", "x")) }()
	select {
	case <-entered:
	case <-time.After(time.Second):
		close(release)
		t.Fatal("request did not reach test ingress")
	}
	w := call(h, requestJSON("custom", "x"))
	if w.Code != 503 {
		t.Error("overload queued or allowed")
	}
	close(release)
	<-done
	if len(h.slots) != 0 {
		t.Fatal("admission slot leaked")
	}
}
