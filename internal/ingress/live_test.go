package ingress

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestLiveProfileAndLongReceipt(t *testing.T) {
	cfg := Config{Gateway: "http://gateway:8080", Secret: testKey, ManagementToken: "test-only", ProbeCandidate: LiveCanary, Profile: "004e-live"}
	h, err := New(cfg)
	if err != nil || h.cfg.Timeout != 44*time.Second {
		t.Fatal("live deadline not installed")
	}
	h.Close()
	for _, mode := range []string{"profile", "timeout", "probe", "negative", "excessive"} {
		bad := cfg
		switch mode {
		case "profile":
			bad.Profile = "unknown"
		case "timeout":
			bad.Timeout = 8 * time.Second
		case "probe":
			bad.ProbeCandidate = testCandidate
		case "negative":
			bad.Timeout = -time.Second
		case "excessive":
			bad.Timeout = time.Hour
		}
		if _, err := New(bad); err == nil {
			t.Fatal("inconsistent live profile accepted")
		}
	}
	nonce := strings.Repeat("a", 64)
	r := fixtureReceipt(nonce)
	now := time.Now()
	// Simulate 35 seconds of verification. Receipt is issued at completion,
	// not request start; replay/stale/future windows remain exactly unchanged.
	if _, err := Verify(sign(r, testKey), testKey, nonce, 200, []byte(testBody), now.Add(-35*time.Second), now); err != nil {
		t.Fatal("long legitimate verification refused")
	}
	r.IssuedAt = now.Add(-21 * time.Second).Unix()
	if _, err := Verify(sign(r, testKey), testKey, nonce, 200, []byte(testBody), now.Add(-35*time.Second), now); err == nil {
		t.Fatal("long request relaxed receipt age")
	}
}

func TestLiveReadinessRequiresAuthenticatedNegativeCanary(t *testing.T) {
	for _, mode := range []string{"valid", "allow", "unsigned", "wrong-candidate"} {
		t.Run(mode, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				switch r.URL.Path {
				case "/health":
					_, _ = w.Write([]byte(`{}`))
				case "/api/plugins/loaded":
					_, _ = w.Write([]byte(`{"plugins":["epochguard"]}`))
				case "/api/plugins":
					_, _ = w.Write([]byte(`{"plugins":[{"name":"epochguard","enabled":true,"placement":"pre_builtin","order":0,"status":{"status":"active"},"config":{"verifier":{"mode":"004b.v1"},"attestation":{"protocol":"004d.v1"}}}]}`))
				case Path:
					body := []byte(`{"error":{"message":"unavailable"}}`)
					receipt := Receipt{Protocol, r.Header.Get(NonceHeader), Policy, "UNAVAILABLE", 503, Hash(body), "", time.Now().Unix()}
					if mode == "allow" {
						body = []byte(testBody)
						receipt = fixtureReceipt(r.Header.Get(NonceHeader))
					}
					if mode != "unsigned" {
						w.Header().Set(ReceiptHeader, sign(receipt, testKey))
					}
					w.WriteHeader(receipt.Status)
					_, _ = w.Write(body)
				}
			}))
			defer server.Close()
			cfg := Config{Gateway: server.URL, Secret: testKey, ManagementToken: "test-only", ProbeCandidate: LiveCanary, Profile: "004e-live"}
			if mode == "wrong-candidate" {
				cfg.ProbeCandidate = testCandidate
			}
			h, err := New(cfg)
			if mode == "wrong-candidate" {
				if err == nil {
					t.Fatal("synthetic live canary accepted")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			defer h.Close()
			recorder := httptest.NewRecorder()
			h.ServeHTTP(recorder, httptest.NewRequest("GET", "/ready", nil))
			if (recorder.Code == 200) != (mode == "valid") {
				t.Fatal("live readiness accepted incorrect enforcement outcome")
			}
		})
	}
}
