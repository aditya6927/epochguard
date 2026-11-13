package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func multiFixture(t *testing.T, caseID string) multiResult {
	t.Helper()
	data, err := os.ReadFile("../../tests/conformance/004b-" + caseID + ".json")
	if err != nil {
		t.Fatal(err)
	}
	var record multiResult
	if err := strictMultiJSON(data, &record); err != nil {
		t.Fatal(err)
	}
	return record
}

func TestMultiGrammarConformance(t *testing.T) {
	data, err := os.ReadFile("../../tests/conformance/004b-grammar.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Text   string       `json:"text"`
		Reason string       `json:"reason"`
		Claims []multiBound `json:"claims"`
	}
	if err := json.Unmarshal(data, &vectors); err != nil {
		t.Fatal(err)
	}
	for i, row := range vectors {
		claims, reason := multiGrammar(row.Text)
		if reason != row.Reason || (len(claims) != 0 && !reflect.DeepEqual(claims, row.Claims)) || len(claims) != len(row.Claims) {
			t.Fatalf("conformance vector %d disagrees", i)
		}
	}
}

func TestMultiRecordConformance(t *testing.T) {
	for _, tc := range []struct {
		caseID string
		want   Decision
	}{{"A", Allow}, {"B", Reject}, {"C", Unavailable}} {
		t.Run(tc.caseID, func(t *testing.T) {
			v := multiFixture(t, tc.caseID)
			req := verificationRequest{multiSchema, multiPolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
			got, err := validateMulti(req, v, "fixture", v.CheckedAt.Add(-time.Second), v.CheckedAt.Add(time.Second))
			if got != tc.want || err != nil {
				t.Fatalf("decision=%s err=%v", got, err)
			}
		})
	}
	v := multiFixture(t, "B")
	v.Claims = v.Claims[1:]
	req := verificationRequest{multiSchema, multiPolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
	if got, err := validateMulti(req, v, "fixture", v.CheckedAt, v.CheckedAt); got != Reject || err != nil {
		t.Fatal("independent contradiction lost when neighboring result absent")
	}
}

func TestMultiTamperingFailsEnforcement(t *testing.T) {
	for _, mutation := range []string{"missing", "duplicate", "reordered", "forged-verdict", "comparison", "hash", "id", "stale", "future", "mode", "url", "policy", "extraction", "binding", "span", "required", "candidate", "requirements", "evidence-id", "schema", "extraction-id"} {
		t.Run(mutation, func(t *testing.T) {
			v := multiFixture(t, "A")
			req := verificationRequest{multiSchema, multiPolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
			switch mutation {
			case "missing":
				v.Claims = v.Claims[:1]
			case "duplicate":
				v.Claims = append(v.Claims, v.Claims[0])
			case "reordered":
				v.Claims[0], v.Claims[1] = v.Claims[1], v.Claims[0]
			case "forged-verdict":
				v.Claims[1].Evidence = []multiEvidence{}
				v.Claims[1].EvidenceRequirementsSatisfied = false
				v.Claims[1].Verdict, v.Claims[1].ReasonCode = "INSUFFICIENT", "RETRIEVAL_FAILURE"
			case "comparison":
				v.Claims[1].Evidence[0].ObservedVersion = "2.88.6"
			case "hash":
				v.CandidateSHA256 = strings.Repeat("0", 64)
			case "id":
				v.RequestID = "wrong"
			case "stale":
				v.Claims[1].Evidence[0].ObservedAt = v.CheckedAt.Add(-61 * time.Second)
				v.Claims[1].Evidence[0].RetrievedAt = v.Claims[1].Evidence[0].ObservedAt
			case "future":
				v.CheckedAt = v.CheckedAt.Add(3 * time.Second)
			case "mode":
				v.Claims[1].Evidence[0].RetrievalMode = "pypi_live"
			case "url":
				v.Claims[1].Evidence[0].URL = primaryURL
			case "policy":
				v.Claims[1].Claim.PolicyID = "attacker"
			case "extraction":
				v.ExtractionStatus = "FAILED"
			case "binding":
				v.BindingStatus = "FAILED"
			case "span":
				v.Claims[1].Claim.Source.Start++
			case "required":
				v.Coverage.RequiredClaimIDs = v.Coverage.RequiredClaimIDs[:1]
			case "candidate":
				v.Candidate += "extra"
			case "requirements":
				v.Claims[1].EvidenceRequirementsSatisfied = false
			case "evidence-id":
				v.Claims[1].Evidence[0].EvidenceID = strings.Repeat("0", 64)
			case "schema":
				v.SchemaVersion = verificationSchema
			case "extraction-id":
				v.Extraction.Claims[1].ClaimID = "c001"
			}
			now := multiFixture(t, "A").CheckedAt
			if got, err := validateMulti(req, v, "fixture", now, now); got != Unavailable || err == nil {
				t.Fatal("tampered record accepted")
			}
		})
	}
}

func TestMultiCanonicalJSON(t *testing.T) {
	v := multiFixture(t, "A")
	data, _ := json.Marshal(v)
	for _, tc := range []struct{ name, from, to string }{
		{"alias", `"verdict":`, `"Verdict":`},
		{"nested-alias", `"observed_version":`, `"Observed_Version":`},
		{"duplicate", `"claim_id":"c001"`, `"claim_id":"c001","claim_id":"c001"`},
		{"escaped-duplicate", `"claim_id":"c001"`, `"claim_id":"c001","claim_\u0069d":"c001"`},
		{"missing-false", `"evidence_requirements_satisfied":true,`, ``},
		{"null-array", `"uncertainty":[]`, `"uncertainty":null`},
		{"null-boolean", `"evidence_requirements_satisfied":true`, `"evidence_requirements_satisfied":null`},
		{"wrong-type", `"start":0`, `"start":"0"`},
		{"unknown", `"policy_id":`, `"unknown":"x","policy_id":`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			mutated := strings.Replace(string(data), tc.from, tc.to, 1)
			if mutated == string(data) {
				t.Fatal("ineffective mutation")
			}
			var out multiResult
			if strictMultiJSON([]byte(mutated), &out) == nil {
				t.Fatal("bad JSON accepted")
			}
		})
	}
	for _, raw := range [][]byte{append(data, []byte(" {}")...), []byte(strings.Repeat(" ", multiBodyLimit+1)), []byte(`null`)} {
		var out multiResult
		if strictMultiJSON(raw, &out) == nil {
			t.Fatal("invalid envelope accepted")
		}
	}
}

func TestMultiHTTPAndCandidateBounds(t *testing.T) {
	v := multiFixture(t, "A")
	text := strings.Repeat(" ", 8192-len(v.Candidate)) + v.Candidate
	// The HTTP path uses freshly generated Python records in end-to-end tests;
	// here confirm >512-byte candidates reach the independent validator, and
	// transport/contract failures still produce a terminal refusal.
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"verdict":"SUPPORTED"}`))
	}))
	defer server.Close()
	source, err := newMultiDecisionSource(HTTPVerificationConfig{Mode: multiSchema, URL: server.URL + "/v1/verify/multiclaim", EvidenceMode: "fixture"})
	if err != nil {
		t.Fatal(err)
	}
	resp := claimCandidate("3.88.7")
	resp.ChatResponse.Choices[0].Message.Content.ContentStr = &text
	answer, failure, ordinary := enforce(context.Background(), resp, nil, source)
	if calls != 1 || answer != nil || failure == nil || *failure.StatusCode != 503 || *failure.AllowFallbacks || ordinary != nil {
		t.Fatal("HTTP/candidate boundary failed")
	}
	text += " "
	_, _, _ = enforce(context.Background(), resp, nil, source)
	if calls != 1 || multiTextBound(strings.Repeat("😀", 8193)) || multiTextBound(string([]byte{0xff})) {
		t.Fatal("candidate bound failed")
	}
	// Preserve genuine provider failure identity in the new mode.
	upstream := &schemas.BifrostError{StatusCode: schemas.Ptr(400)}
	_, got, _ := enforce(context.Background(), resp, upstream, source)
	if got != upstream || calls != 1 {
		t.Fatal("provider error changed")
	}
}

func TestMultiConfiguration(t *testing.T) {
	for _, tc := range []struct{ mode, path, evidence string }{
		{multiSchema, "/v1/verify", "fixture"}, {"unknown", "/v1/verify/multiclaim", "fixture"},
		{multiSchema, "/v1/verify/multiclaim", "tavily_live"}, {multiSchema, "/v1/verify/multiclaim", ""},
	} {
		if _, err := newMultiDecisionSource(HTTPVerificationConfig{Mode: tc.mode, URL: "http://verifier" + tc.path, EvidenceMode: tc.evidence}); err == nil {
			t.Fatal("mixed configuration accepted")
		}
	}
	if _, err := newHTTPDecisionSource(HTTPVerificationConfig{Mode: multiSchema, URL: "http://verifier/v1/verify"}); err == nil {
		t.Fatal("legacy constructor accepted new mode")
	}
	if err := configure(map[string]any{"test_only": true, "verifier": map[string]any{"mode": multiSchema, "url": "http://verifier/v1/verify/multiclaim", "evidence_mode": "fixture"}}); err != nil {
		t.Fatal(err)
	}
	if _, ok := activePolicy.Load().source.(*multiDecisionSource); !ok {
		t.Fatal("wrong source installed")
	}
	if err := configure(map[string]any{"test_only": true, "verifier": map[string]any{"mode": multiSchema, "url": "http://verifier/v1/verify", "evidence_mode": "fixture"}}); err == nil || activePolicy.Load() != nil {
		t.Fatal("failed configuration retained prior source")
	}
}

func TestMultiMixedResponseDoesNotReachVerifier(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("mixed response reached verifier")
	}))
	defer server.Close()
	source, err := newMultiDecisionSource(HTTPVerificationConfig{Mode: multiSchema, URL: server.URL + "/v1/verify/multiclaim", EvidenceMode: "fixture"})
	if err != nil {
		t.Fatal(err)
	}
	resp := claimCandidate("3.88.7")
	resp.TextCompletionResponse = &schemas.BifrostTextCompletionResponse{}
	if got, err := source.Decide(context.Background(), resp); got != Unavailable || err == nil {
		t.Fatal("mixed pointer union accepted")
	}
}
