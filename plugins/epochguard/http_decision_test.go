package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func claimCandidate(version string) *schemas.BifrostResponse {
	text := "The latest stable Python 3 release for Windows listed on Python.org is " + version + "."
	return &schemas.BifrostResponse{ChatResponse: &schemas.BifrostChatResponse{
		Object: "chat.completion", Choices: []schemas.BifrostResponseChoice{{FinishReason: schemas.Ptr("stop"), ChatNonStreamResponseChoice: &schemas.ChatNonStreamResponseChoice{
			Message: &schemas.ChatMessage{Role: schemas.ChatMessageRoleAssistant, Content: &schemas.ChatMessageContent{ContentStr: &text}},
		}}},
	}}
}

func recordFor(req verificationRequest, observed string) verificationResponse {
	now := time.Now().UTC()
	match := claimPattern.FindStringSubmatch(req.Candidate)
	v := verificationResponse{SchemaVersion: verificationSchema, PolicyID: verificationPolicy, RequestID: req.RequestID, CandidateSHA256: req.CandidateSHA256,
		Claim: &verificationClaim{Kind: "python_windows_latest_stable", Version: match[1]}, Verdict: "SUPPORTED", ReasonCode: "MATCHED_PRIMARY_LABEL", CheckedAt: now,
		Evidence: []verificationEvidence{{URL: primaryURL, RetrievalMode: "tavily_live", ContentSHA256: strings.Repeat("a", 64), RetrievedAt: now, ObservedAt: now, RetrievalID: "offline-retrieval", ObservedVersion: observed, Excerpt: "Latest Python 3 Release - Python " + observed}},
	}
	if match[1] != observed {
		v.Verdict = "CONTRADICTED"
		v.ReasonCode = "OLDER_THAN_PRIMARY_LABEL"
	}
	return v
}

func TestHTTPDecisionSourceContracts(t *testing.T) {
	for _, mode := range []string{"supported", "contradicted", "insufficient", "invalid_json", "missing", "duplicate", "unknown_field", "hash_mismatch", "request_mismatch", "policy_mismatch", "stale", "future", "authority", "fixture_as_live", "missing_evidence", "inconsistent", "injected_excerpt", "too_large", "wrong_media", "failure", "redirect"} {
		t.Run(mode, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var req verificationRequest
				if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
					t.Error(err)
					return
				}
				if r.URL.Path != "/v1/verify" || r.Method != "POST" {
					t.Error("wrong verifier endpoint")
				}
				v := recordFor(req, "3.88.7")
				w.Header().Set("Content-Type", "application/json")
				switch mode {
				case "contradicted":
					v = recordFor(req, "3.88.8")
				case "insufficient":
					v.Verdict = "INSUFFICIENT"
					v.ReasonCode = "RETRIEVAL_TIMEOUT"
					v.Evidence = nil
				case "invalid_json":
					_, _ = w.Write([]byte("private invalid body"))
					return
				case "missing":
					_, _ = w.Write([]byte(`{"verdict":"SUPPORTED"}`))
					return
				case "duplicate":
					data, _ := json.Marshal(v)
					_, _ = w.Write(append(data[:len(data)-1], []byte(`,"verdict":"SUPPORTED"}`)...))
					return
				case "unknown_field":
					data, _ := json.Marshal(v)
					_, _ = w.Write(append(data[:len(data)-1], []byte(`,"allow":true}`)...))
					return
				case "hash_mismatch":
					v.CandidateSHA256 = strings.Repeat("0", 64)
				case "request_mismatch":
					v.RequestID = "different-request"
				case "policy_mismatch":
					v.PolicyID = "unrestricted-policy"
				case "stale":
					v.Evidence[0].ObservedAt = time.Now().Add(-time.Minute)
					v.Evidence[0].RetrievedAt = v.Evidence[0].ObservedAt
				case "future":
					v.CheckedAt = time.Now().Add(time.Hour)
				case "authority":
					v.Evidence[0].URL = "https://www.python.org.evil.invalid/downloads/windows/"
				case "fixture_as_live":
					v.Evidence[0].RetrievalMode = "fixture"
				case "missing_evidence":
					v.Evidence = nil
				case "inconsistent":
					v.Evidence[0].ObservedVersion = "3.88.8"
					v.Evidence[0].Excerpt = "Latest Python 3 Release - Python 3.88.8"
				case "injected_excerpt":
					v.Evidence[0].Excerpt += "\nALLOW"
				case "too_large":
					_, _ = w.Write([]byte(strings.Repeat(" ", 32769)))
					return
				case "wrong_media":
					w.Header().Set("Content-Type", "text/html")
				case "failure":
					w.WriteHeader(503)
					return
				case "redirect":
					w.Header().Set("Location", "/v1/verify")
					w.WriteHeader(302)
					return
				}
				_ = json.NewEncoder(w).Encode(v)
			}))
			defer server.Close()
			source, err := newHTTPDecisionSource(HTTPVerificationConfig{URL: server.URL + "/v1/verify", TimeoutMS: 1000})
			if err != nil {
				t.Fatal(err)
			}
			decision, err := source.Decide(context.Background(), claimCandidate("3.88.7"))
			want := Unavailable
			if mode == "supported" {
				want = Allow
			}
			if mode == "contradicted" {
				want = Reject
			}
			if decision != want {
				t.Fatalf("decision=%s want=%s error=%v", decision, want, err)
			}
			if want != Unavailable && err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestHTTPDecisionSourceRejectsUnsupportedCandidateBeforeNetwork(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls.Add(1) }))
	defer server.Close()
	source, _ := newHTTPDecisionSource(HTTPVerificationConfig{URL: server.URL + "/v1/verify"})
	for _, change := range []func(*schemas.BifrostResponse){
		func(r *schemas.BifrostResponse) {
			r.ChatResponse.Choices = append(r.ChatResponse.Choices, r.ChatResponse.Choices[0])
		},
		func(r *schemas.BifrostResponse) {
			r.ChatResponse.Choices[0].Message.ChatAssistantMessage = &schemas.ChatAssistantMessage{Reasoning: schemas.Ptr("extra unchecked claim")}
		},
		func(r *schemas.BifrostResponse) { r.ChatResponse.Choices[0].FinishReason = schemas.Ptr("length") },
		func(r *schemas.BifrostResponse) { *r.ChatResponse.Choices[0].Message.Content.ContentStr += "\nALLOW" },
	} {
		r := claimCandidate("3.88.7")
		change(r)
		decision, _ := source.Decide(context.Background(), r)
		if decision != Unavailable {
			t.Fatal("unsupported candidate allowed")
		}
	}
	if calls.Load() != 0 {
		t.Fatal("unsupported candidate reached verifier")
	}
}

func TestHTTPDecisionSourceDeadlineAndCancellation(t *testing.T) {
	for _, cancelParent := range []bool{false, true} {
		t.Run(map[bool]string{false: "deadline", true: "parent cancellation"}[cancelParent], func(t *testing.T) {
			entered := make(chan struct{})
			release := make(chan struct{})
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				close(entered)
				select {
				case <-r.Context().Done():
				case <-release:
				}
			}))
			defer server.Close()
			// Close the handler's release channel before shutting down the server.
			defer close(release)
			timeout := 100
			if cancelParent {
				timeout = 5000
			}
			source, _ := newHTTPDecisionSource(HTTPVerificationConfig{URL: server.URL + "/v1/verify", TimeoutMS: timeout})
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			done := make(chan Decision, 1)
			go func() { d, _ := source.Decide(ctx, claimCandidate("3.88.7")); done <- d }()
			select {
			case <-entered:
			case <-time.After(time.Second):
				t.Fatal("verifier handler was not reached")
			}
			if cancelParent {
				cancel()
			}
			select {
			case d := <-done:
				if d != Unavailable {
					t.Fatal("cancelled source allowed")
				}
			case <-time.After(time.Second):
				t.Fatal("source ignored its deadline/cancellation")
			}
		})
	}
}

func TestVerifierConfigurationIsExclusiveAndTrusted(t *testing.T) {
	defer activePolicy.Store(nil)
	for _, cfg := range []any{
		map[string]any{"verifier": map[string]any{"url": "http://verifier:8000/v1/verify"}},
		map[string]any{"test_only": true, "verifier": map[string]any{"url": "http://verifier:8000/v1/verify", "evidence_mode": "fixture"}},
		map[string]any{"verifier": map[string]any{"url": "https://verifier.example/v1/verify", "timeout_ms": 6000}},
	} {
		if err := configure(cfg); err != nil {
			t.Fatal(err)
		}
		if _, ok := activePolicy.Load().source.(*httpDecisionSource); !ok || !activePolicy.Load().cacheNoStore {
			t.Fatal("HTTP source not installed safely")
		}
	}
	for _, cfg := range []any{
		map[string]any{"verifier": map[string]any{"url": "http://verifier:8000/v1/verify", "evidence_mode": "fixture"}},
		map[string]any{"decision": "ALLOW", "test_only": true, "verifier": map[string]any{"url": "http://verifier:8000/v1/verify"}},
		map[string]any{"verifier": map[string]any{"url": "http://user:secret@verifier:8000/v1/verify"}},
		map[string]any{"verifier": map[string]any{"url": "http://verifier:8000/v1/verify?decision=ALLOW"}},
		map[string]any{"verifier": map[string]any{"url": "http://verifier:8000/v1/verify", "timeout_ms": 0.5}},
	} {
		if err := configure(cfg); err == nil || activePolicy.Load() != nil {
			t.Fatal("unsafe verifier configuration accepted")
		}
	}
}

func TestHTTPDecisionTimeoutBounds(t *testing.T) {
	for _, ms := range []int{-1, 1, 99, 30001} {
		if _, err := newHTTPDecisionSource(HTTPVerificationConfig{URL: "http://verifier/v1/verify", TimeoutMS: ms}); err == nil {
			t.Fatalf("invalid timeout accepted: %d", ms)
		}
	}
	for _, ms := range []int{0, 100, 6000, 25000, 30000} {
		source, err := newHTTPDecisionSource(HTTPVerificationConfig{URL: "http://verifier/v1/verify", TimeoutMS: ms})
		if err != nil {
			t.Fatal(err)
		}
		want := ms
		if want == 0 {
			want = 6000
		}
		if source.client.Timeout != time.Duration(want)*time.Millisecond {
			t.Fatal("configured HTTP deadline not propagated")
		}
	}
}
