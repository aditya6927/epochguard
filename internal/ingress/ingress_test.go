package ingress

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

var testKey = bytes.Repeat([]byte{7}, 32) // isolated test key, never a deployment credential
const testCandidate = "The latest stable Python 3 release for Windows listed on Python.org is 3.88.7."
const testBody = `{"choices":[{"message":{"content":"` + testCandidate + `"}}]}`
const testRequest = `{"model":"fixture/epochguard-test","messages":[{"role":"user","content":"candidate"}],"stream":false}`

func sign(r Receipt, key []byte) string {
	payload, _ := json.Marshal(r)
	mac := hmac.New(sha256.New, key)
	_, _ = mac.Write(payload)
	return base64.RawURLEncoding.EncodeToString(payload) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}
func fixtureReceipt(nonce string) Receipt {
	return Receipt{Protocol, nonce, Policy, "ALLOW", 200, Hash([]byte(testBody)), Hash([]byte(testCandidate)), time.Now().Unix()}
}

func TestReceiptAdversaries(t *testing.T) {
	nonce := strings.Repeat("a", 64)
	for _, mode := range []string{"valid", "mac", "key", "nonce", "body", "status", "version", "policy", "stale", "future", "outcome", "candidate", "missing", "alias", "duplicate", "extra", "null"} {
		t.Run(mode, func(t *testing.T) {
			r := fixtureReceipt(nonce)
			body := []byte(testBody)
			status := 200
			key := testKey
			switch mode {
			case "nonce":
				r.Nonce = strings.Repeat("b", 64)
			case "body":
				body = append(body, ' ')
			case "status":
				status = 201
			case "version":
				r.Version = "wrong"
			case "policy":
				r.PolicyID = "wrong"
			case "stale":
				r.IssuedAt -= 21
			case "future":
				r.IssuedAt += 3
			case "outcome":
				r.Outcome = "loaded"
			case "candidate":
				r.CandidateSHA256 = strings.Repeat("0", 64)
			case "key":
				key = bytes.Repeat([]byte{8}, 32)
			}
			header := sign(r, key)
			if mode == "mac" {
				header = header[:len(header)-2] + "ab"
			}
			if mode == "missing" {
				header = ""
			}
			if mode == "alias" || mode == "duplicate" || mode == "extra" || mode == "null" {
				payload, _ := json.Marshal(r)
				text := string(payload)
				switch mode {
				case "alias":
					text = strings.Replace(text, `"version":`, `"Version":`, 1)
				case "duplicate":
					text = strings.Replace(text, `"version":`, `"version":"004d.v1","version":`, 1)
				case "extra":
					text = strings.Replace(text, `"version":`, `"unknown":true,"version":`, 1)
				case "null":
					text = strings.Replace(text, `"status":200`, `"status":null`, 1)
				}
				mac := hmac.New(sha256.New, testKey)
				_, _ = mac.Write([]byte(text))
				header = base64.RawURLEncoding.EncodeToString([]byte(text)) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
			}
			_, err := Verify(header, testKey, nonce, status, body, time.Now().Add(-time.Second), time.Now())
			if (err == nil) != (mode == "valid") {
				t.Fatal("receipt security boundary disagreed")
			}
		})
	}
}

func TestAuthenticatedOutcomes(t *testing.T) {
	for _, tc := range []struct {
		outcome string
		status  int
	}{{"REJECT", 403}, {"UNAVAILABLE", 503}, {"PROVIDER_ERROR", 400}} {
		r := fixtureReceipt(strings.Repeat("b", 64))
		r.Outcome, r.Status, r.CandidateSHA256 = tc.outcome, tc.status, ""
		if _, err := Verify(sign(r, testKey), testKey, r.Nonce, r.Status, []byte(testBody), time.Now(), time.Now()); err != nil {
			t.Fatal("valid authenticated outcome refused")
		}
	}
}

func TestIngressConfigurationFailsClosed(t *testing.T) {
	for _, mode := range []string{"missing-key", "short-key", "token", "probe", "endpoint", "scheme", "timeout", "concurrency"} {
		cfg := Config{Gateway: "http://gateway:8080", Secret: testKey, ManagementToken: "local-test-only", ProbeCandidate: testCandidate}
		switch mode {
		case "missing-key":
			cfg.Secret = nil
		case "short-key":
			cfg.Secret = testKey[:31]
		case "token":
			cfg.ManagementToken = ""
		case "probe":
			cfg.ProbeCandidate = ""
		case "endpoint":
			cfg.Gateway += "/other"
		case "scheme":
			cfg.Gateway = "ftp://gateway"
		case "timeout":
			cfg.Timeout = time.Millisecond
		case "concurrency":
			cfg.MaxActive = 33
		}
		if h, err := New(cfg); err == nil {
			h.Close()
			t.Fatal("invalid deployment configuration accepted")
		}
	}
}

func newTestHandler(t *testing.T, url string) *Handler {
	t.Helper()
	h, err := New(Config{Gateway: url, Secret: testKey, ManagementToken: "local-test-only", ProbeCandidate: testCandidate, Timeout: 500 * time.Millisecond, MaxActive: 4})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(h.Close)
	return h
}

func TestIngressBuffersAndStripsSpoofedHeaders(t *testing.T) {
	var seen string
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = r.Header.Get(NonceHeader)
		if len(r.Header.Values(NonceHeader)) != 1 || seen == strings.Repeat("a", 64) || r.Header.Get(ReceiptHeader) != "" || r.Header.Get("X-Bifrost-Setup-Token") != "" || r.Header.Get("X-Bf-Send-Back-Raw-Response") != "" {
			t.Error("client internal headers crossed ingress")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set(ReceiptHeader, sign(fixtureReceipt(seen), testKey))
		w.Header().Set("X-EpochGuard-Verified", "fake")
		w.Header().Set("Set-Cookie", "untrusted")
		_, _ = w.Write([]byte(testBody))
	}))
	defer up.Close()
	h := newTestHandler(t, up.URL)
	r := httptest.NewRequest("POST", Path, strings.NewReader(testRequest))
	r.Header.Set("Content-Type", "application/json")
	r.Header["x-epochguard-internal-nonce"] = []string{strings.Repeat("a", 64), strings.Repeat("b", 64)}
	r.Header.Set(ReceiptHeader, "spoof")
	r.Header.Set("X-Bifrost-Setup-Token", "spoof")
	r.Header.Set("X-Bf-Send-Back-Raw-Response", "true")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 200 || w.Body.String() != testBody || seen == "" || w.Header().Get(ReceiptHeader) != "" || w.Header().Get("X-EpochGuard-Verified") != "" || w.Header().Get("Set-Cookie") != "" {
		t.Fatal("protected release or header boundary failed")
	}
}

func TestMalformedRequestsNeverDispatch(t *testing.T) {
	var count atomic.Int64
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { count.Add(1) }))
	defer up.Close()
	h := newTestHandler(t, up.URL)
	for _, target := range []string{"/api/plugins", "/v1/chat/completions", "/openai/v1/chat/completions/", "/openai/v1/%63hat/completions", Path + "?x=1", "//openai/v1/chat/completions"} {
		r := httptest.NewRequest("POST", target, strings.NewReader(testRequest))
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 400 {
			t.Fatal("unsupported target accepted")
		}
	}
	for _, data := range []string{strings.Repeat("x", 65537), `{"model":"x","Model":"x"}`, strings.Replace(testRequest, `"stream":false`, `"stream":true`, 1), strings.Replace(testRequest, `"stream":false`, `"Stream":false`, 1), strings.Replace(testRequest, `"stream":false`, `"stream":false,"stream":false`, 1), strings.Replace(testRequest, `"stream":false`, `"stream":null`, 1), strings.Replace(testRequest, `"stream":false`, `"tools":[]`, 1)} {
		r := httptest.NewRequest("POST", Path, strings.NewReader(data))
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 400 && w.Code != 413 {
			t.Fatal("malformed request accepted")
		}
	}
	for _, mode := range []string{"GET", "async", "content-type", "encoding", "duplicate-type"} {
		r := httptest.NewRequest("POST", Path, strings.NewReader(testRequest))
		r.Header.Set("Content-Type", "application/json")
		switch mode {
		case "GET":
			r.Method = "GET"
		case "async":
			r.Header.Set("X-Bf-Async", "true")
		case "content-type":
			r.Header.Set("Content-Type", "text/plain")
		case "encoding":
			r.Header.Set("Content-Encoding", "gzip")
		case "duplicate-type":
			r.Header.Add("Content-Type", "application/json")
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 400 {
			t.Fatal("unsupported request accepted")
		}
	}
	if count.Load() != 0 {
		t.Fatal("invalid request reached gateway")
	}
}

func TestResponseFailuresNeverLeak(t *testing.T) {
	for _, mode := range []string{"missing", "wrong", "mutated", "status", "duplicate", "oversized", "partial", "stalled", "redirect"} {
		t.Run(mode, func(t *testing.T) {
			up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				receipt := sign(fixtureReceipt(r.Header.Get(NonceHeader)), testKey)
				if mode != "missing" {
					w.Header().Set(ReceiptHeader, receipt)
				}
				if mode == "wrong" {
					w.Header().Set(ReceiptHeader, "invalid")
				}
				if mode == "duplicate" {
					w.Header().Add(ReceiptHeader, receipt)
				}
				if mode == "status" {
					w.WriteHeader(201)
				}
				if mode == "redirect" {
					w.Header().Set("Location", upstreamRedirect)
					w.WriteHeader(302)
				}
				if mode == "oversized" {
					_, _ = w.Write([]byte(strings.Repeat("x", ResponseLimit+1)))
					return
				}
				if mode == "stalled" {
					w.(http.Flusher).Flush()
					<-r.Context().Done()
					return
				}
				if mode == "partial" {
					w.Header().Set("Content-Length", "10000")
				}
				_, _ = w.Write([]byte(testBody))
				if mode == "mutated" {
					_, _ = w.Write([]byte(" "))
				}
			}))
			defer up.Close()
			h := newTestHandler(t, up.URL)
			r := httptest.NewRequest("POST", Path, strings.NewReader(testRequest))
			r.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code != 503 || strings.Contains(w.Body.String(), testCandidate) || w.Header().Get(ReceiptHeader) != "" {
				t.Fatal("unchecked response leaked")
			}
		})
	}
}

const upstreamRedirect = "http://untrusted.invalid/"

func TestConcurrentNonceReplayAndAdmission(t *testing.T) {
	var mu sync.Mutex
	nonces := map[string]bool{}
	entered, release := make(chan struct{}, 16), make(chan struct{})
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		nonce := r.Header.Get(NonceHeader)
		mu.Lock()
		if nonces[nonce] {
			t.Error("nonce reused")
		}
		nonces[nonce] = true
		mu.Unlock()
		entered <- struct{}{}
		select {
		case <-release:
		case <-r.Context().Done():
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set(ReceiptHeader, sign(fixtureReceipt(nonce), testKey))
		_, _ = w.Write([]byte(testBody))
	}))
	defer up.Close()
	h := newTestHandler(t, up.URL)
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := httptest.NewRequest("POST", Path, strings.NewReader(testRequest))
			r.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code != 200 {
				t.Error("concurrent valid response refused")
			}
		}()
	}
	for i := 0; i < 4; i++ {
		<-entered
	}
	r := httptest.NewRequest("POST", Path, strings.NewReader(testRequest))
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 503 {
		t.Fatal("unbounded admission")
	}
	close(release)
	wg.Wait()
	old := fixtureReceipt(strings.Repeat("a", 64))
	if _, err := Verify(sign(old, testKey), testKey, strings.Repeat("b", 64), 200, []byte(testBody), time.Now(), time.Now()); err == nil {
		t.Fatal("cross-request replay accepted")
	}
}

func TestGatewayDisconnectCancelsWork(t *testing.T) {
	entered, done := make(chan struct{}), make(chan struct{})
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		close(entered)
		<-r.Context().Done()
		close(done)
	}))
	defer up.Close()
	h := newTestHandler(t, up.URL)
	server := httptest.NewServer(h)
	defer server.Close()
	req, _ := http.NewRequest("POST", server.URL+Path, strings.NewReader(testRequest))
	req.Header.Set("Content-Type", "application/json")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	finished := make(chan error, 1)
	go func() {
		response, err := http.DefaultClient.Do(req.WithContext(ctx))
		if response != nil {
			response.Body.Close()
		}
		finished <- err
	}()
	<-entered
	cancel()
	if <-finished == nil {
		t.Fatal("cancelled client unexpectedly received a response")
	}
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("gateway work not cancelled")
	}
}
