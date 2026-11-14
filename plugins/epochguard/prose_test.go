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
)

func TestProseHTTPConfiguration(t *testing.T) {
	v := proseFixture(t, "A")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req verificationRequest
		if json.NewDecoder(r.Body).Decode(&req) != nil || req.SchemaVersion != proseSchema || req.PolicyID != prosePolicy || r.URL.Path != "/v1/verify/prose" {
			t.Error("wrong request binding")
		}
		v.RequestID, v.Verification.RequestID = req.RequestID, req.RequestID
		now := time.Now()
		v.Verification.CheckedAt = now
		for i := range v.Verification.Claims {
			for j := range v.Verification.Claims[i].Evidence {
				v.Verification.Claims[i].Evidence[j].ObservedAt = now
				v.Verification.Claims[i].Evidence[j].RetrievedAt = now
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(v)
	}))
	defer server.Close()
	cfg := HTTPVerificationConfig{Mode: proseSchema, URL: server.URL + "/v1/verify/prose", EvidenceMode: "fixture"}
	source, err := newProseDecisionSource(cfg)
	if err != nil {
		t.Fatal(err)
	}
	response := claimCandidate("3.15.2")
	response.ChatResponse.Choices[0].Message.Content.ContentStr = &v.Candidate
	if got, err := source.Decide(context.Background(), response); got != Allow || err != nil {
		t.Fatal(got, err)
	}
	for _, mode := range []string{"", multiSchema, verificationSchema} {
		cfg.Mode = mode
		if _, err := newProseDecisionSource(cfg); err == nil {
			t.Fatal("cross-mode configuration accepted")
		}
	}
	cfg.Mode = proseSchema
	cfg.URL = server.URL + "/v1/verify/multiclaim"
	if _, err := newProseDecisionSource(cfg); err == nil {
		t.Fatal("wrong endpoint")
	}
	cfg.URL = server.URL + "/v1/verify/prose"
	cfg.EvidenceMode = "live"
	cfg.TimeoutProfile = "004e-live"
	cfg.TimeoutMS = 30000
	if _, err := newProseDecisionSource(cfg); err != nil {
		t.Fatal(err)
	}
	cfg.EvidenceMode = "fixture"
	if _, err := newProseDecisionSource(cfg); err == nil {
		t.Fatal("fixture accepted live profile")
	}
}

func TestProseConformance(t *testing.T) {
	data, err := os.ReadFile("../../tests/conformance/004g-grammar.json")
	if err != nil {
		t.Fatal(err)
	}
	var rows []struct {
		Text     string
		Reason   string
		Mappings []proseMapping
	}
	if json.Unmarshal(data, &rows) != nil {
		t.Fatal("fixtures")
	}
	for i, row := range rows {
		mappings, reason := proseGrammar(row.Text)
		if reason != row.Reason || len(mappings) != len(row.Mappings) || len(mappings) > 0 && !reflect.DeepEqual(mappings, row.Mappings) {
			t.Fatalf("vector %d", i)
		}
	}
}

func proseFixture(t *testing.T, name string) proseResult {
	t.Helper()
	data, err := os.ReadFile("../../tests/conformance/004g-" + name + ".json")
	if err != nil {
		t.Fatal(err)
	}
	var v proseResult
	if err := strictRecordJSON(data, &v, 10); err != nil {
		t.Fatal(err)
	}
	return v
}
func TestProseContracts(t *testing.T) {
	for _, row := range []struct {
		name string
		want Decision
	}{{"A", Allow}, {"B", Reject}, {"C", Unavailable}} {
		v := proseFixture(t, row.name)
		req := verificationRequest{proseSchema, prosePolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
		now := time.Now()
		if v.Verification != nil {
			now = v.Verification.CheckedAt
		}
		got, err := validateProse(req, v, "fixture", now.Add(-time.Second), now)
		if got != row.want || err != nil {
			t.Fatalf("%s %s %v", row.name, got, err)
		}
	}
}
func TestProseTampering(t *testing.T) {
	for _, mutation := range []string{"offset", "text", "policy", "version", "canonical", "missing", "order", "coverage", "hash", "original", "evidence", "mode", "id", "stale", "verdict"} {
		t.Run(mutation, func(t *testing.T) {
			v := proseFixture(t, "A")
			now := v.Verification.CheckedAt
			req := verificationRequest{proseSchema, prosePolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
			switch mutation {
			case "offset":
				v.Mappings[0].Start++
			case "text":
				v.Mappings[0].SourceText += "x"
			case "policy":
				v.Mappings[0].PolicyID = pypiPolicy
			case "version":
				v.Mappings[0].Version = "3.15.1"
			case "canonical":
				v.Mappings[0].Canonical += "x"
			case "missing":
				v.Verification.Claims = v.Verification.Claims[:1]
			case "order":
				v.Verification.Claims[0], v.Verification.Claims[1] = v.Verification.Claims[1], v.Verification.Claims[0]
			case "coverage":
				v.Coverage = "UNCERTAIN"
			case "hash":
				v.CandidateSHA256 = strings.Repeat("0", 64)
			case "original":
				v.Candidate += "\nExtra."
				req.Candidate = v.Candidate
				req.CandidateSHA256 = shaText(v.Candidate)
				v.CandidateSHA256 = req.CandidateSHA256
			case "evidence":
				v.Verification.Claims[0].Evidence[0].URL = pypiURL
			case "mode":
				v.Verification.Claims[0].Evidence[0].RetrievalMode = "tavily_live"
			case "id":
				v.RequestID = "other"
			case "stale":
				v.Verification.Claims[0].Evidence[0].ObservedAt = now.Add(-time.Minute * 2)
			case "verdict":
				v.Verification.Claims[0].Verdict = "CONTRADICTED"
			}
			if got, _ := validateProse(req, v, "fixture", now.Add(-time.Second), now); got != Unavailable {
				t.Fatal("tampering authorized")
			}
		})
	}
	v := proseFixture(t, "A")
	data, _ := json.Marshal(v)
	for _, bad := range []string{strings.Replace(string(data), `"coverage":`, `"unknown":0,"coverage":`, 1), strings.Replace(string(data), `"coverage":`, `"coverage":"COMPLETE","coverage":`, 1), strings.Replace(string(data), `"start":0`, `"start":0.0`, 1)} {
		if strictRecordJSON([]byte(bad), &v, 10) == nil {
			t.Fatal("noncanonical wire accepted")
		}
	}
}
