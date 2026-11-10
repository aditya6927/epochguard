package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// Exercise the real HTTP -> typed record -> enforcement path. Each mutation
// would otherwise decode as an internally consistent SUPPORTED record.
func TestVerificationCanonicalFieldNames(t *testing.T) {
	for _, mutation := range []struct{ name, old, replacement string }{
		{"top alias", `"verdict":"SUPPORTED"`, `"Verdict":"SUPPORTED"`},
		{"alias overrides verdict", `"verdict":"SUPPORTED"`, `"verdict":"CONTRADICTED","Verdict":"SUPPORTED"`},
		{"alias first", `"verdict":"SUPPORTED"`, `"VERDICT":"CONTRADICTED","verdict":"SUPPORTED"`},
		{"nested claim", `"version":"3.88.7"`, `"version":"3.0.0","Version":"3.88.7"`},
		{"nested evidence alias", `"observed_version":"3.88.7"`, `"Observed_Version":"3.88.7"`},
		{"nested evidence duplicate", `"url":`, `"URL":"https://evil.invalid/","url":`},
		{"unicode fold", `"schema_version":`, `"\u017fchema_version":`},
		{"escaped canonical duplicate", `"verdict":"SUPPORTED"`, `"verdict":"CONTRADICTED","\u0076erdict":"SUPPORTED"`},
		{"nested exact duplicate", `"version":"3.88.7"`, `"version":"3.0.0","version":"3.88.7"`},
		{"nested unknown", `"version":"3.88.7"`, `"version":"3.88.7","other":true`},
	} {
		t.Run(mutation.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var request verificationRequest
				if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
					t.Error(err)
					return
				}
				data, _ := json.Marshal(recordFor(request, "3.88.7"))
				if !strings.Contains(string(data), mutation.old) {
					t.Error("mutation did not apply")
				}
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(strings.Replace(string(data), mutation.old, mutation.replacement, 1)))
			}))
			defer server.Close()
			source, err := newHTTPDecisionSource(HTTPVerificationConfig{URL: server.URL + "/v1/verify"})
			if err != nil {
				t.Fatal(err)
			}
			decision, decodeErr := source.Decide(context.Background(), claimCandidate("3.88.7"))
			if decision != Unavailable || decodeErr == nil {
				t.Fatalf("ambiguous contract accepted: decision=%s error=%v", decision, decodeErr)
			}
			resp, refusal, hookErr := enforce(context.Background(), claimCandidate("3.88.7"), nil, source)
			if resp != nil || refusal == nil || *refusal.StatusCode != 503 || *refusal.AllowFallbacks || hookErr != nil {
				t.Fatal("invalid contract must produce a terminal 503 without a candidate")
			}
		})
	}
}
