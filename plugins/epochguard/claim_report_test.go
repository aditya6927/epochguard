package main

import (
	"encoding/json"
	"os"
	"testing"
	"time"
)

// Scores are separate operator artifacts. Exercise the actual independent Go
// validation on every fixed 005D Python vector, including malformed bindings.
func TestClaimReportsCannotAuthorize(t *testing.T) {
	data, err := os.ReadFile("../../tests/conformance/005d-reporting.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Name     string          `json:"name"`
		Expected string          `json:"expected"`
		Result   json.RawMessage `json:"result"`
		Report   map[string]any  `json:"report"`
	}
	if json.Unmarshal(data, &vectors) != nil || len(vectors) != 23 {
		t.Fatal("invalid fixed reporting corpus")
	}
	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	for _, vector := range vectors {
		t.Run(vector.Name, func(t *testing.T) {
			var result proseResult
			if strictRecordJSON(vector.Result, &result, 10) != nil {
				t.Fatal("unexpected fixture wire shape")
			}
			req := verificationRequest{proseSchema, prosePolicy, result.RequestID, result.Candidate, shaText(result.Candidate)}
			want := map[string]Decision{"ALLOW": Allow, "REJECT": Reject, "UNAVAILABLE": Unavailable}[vector.Expected]
			check := func() {
				t.Helper()
				got, _ := validateProse(req, result, "fixture", now.Add(-time.Second), now)
				if got != want {
					t.Fatalf("protected decision changed for %s", vector.Name)
				}
			}
			check()
			vector.Report["authorization"] = true
			for _, claim := range vector.Report["claims"].([]any) {
				claim.(map[string]any)["freshness_score"] = 100
			}
			check()
			vector.Report = nil // A report-generation failure is also non-authorizing.
			check()
			// A diagnostic score cannot be smuggled into the evidence wire record.
			var injected map[string]any
			if json.Unmarshal(vector.Result, &injected) != nil {
				t.Fatal("fixture")
			}
			injected["freshness_score"] = 100
			wire, _ := json.Marshal(injected)
			if strictRecordJSON(wire, &proseResult{}, 10) == nil {
				t.Fatal("diagnostic field entered authorization contract")
			}
		})
	}
}
