package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCombinedDiagnosticsPreserveSourceAndReceiptRestrictions(t *testing.T) {
	defer activePolicy.Store(nil)
	path := filepath.Join(t.TempDir(), "fixture-key")
	if os.WriteFile(path, []byte(strings.Repeat("a", 64)), 0600) != nil {
		t.Fatal("fixture key unavailable")
	}
	for _, mode := range []string{"fixture", "live"} {
		config := func() map[string]any {
			verifier := map[string]any{"url": "http://verifier:8000/v1/verify/prose", "mode": proseSchema, "evidence_mode": mode, "timeout_ms": 30000}
			if mode == "live" {
				verifier["timeout_profile"] = "004e-live"
			}
			return map[string]any{"test_only": mode == "fixture", "verifier": verifier,
				"combined_qualification_diagnostics": true,
				"attestation":                        map[string]any{"protocol": boundReceiptVersion, "secret_file": path}}
		}
		if err := configure(config()); err != nil {
			t.Fatal("explicit combined telemetry refused")
		}
		policy := activePolicy.Load()
		if policy == nil || policy.qualification == nil || policy.receiptPolicy != proseSchema+"/"+prosePolicy || policy.attestation == nil {
			t.Fatal("combined diagnostics changed policy identity")
		}
		if policy.source.(*multiDecisionSource).evidenceMode != mode {
			t.Fatal("diagnostics changed source mode")
		}
		for _, mutation := range []string{"legacy", "mode", "test-mode", "both-flags"} {
			value := config()
			switch mutation {
			case "legacy":
				value["attestation"].(map[string]any)["protocol"] = receiptVersion
			case "mode":
				value["verifier"].(map[string]any)["mode"] = multiSchema
			case "test-mode":
				value["test_only"] = mode != "fixture"
			case "both-flags":
				value["qualification_diagnostics"] = true
			}
			if configure(value) == nil || activePolicy.Load() != nil {
				t.Fatal("invalid combined configuration retained authorization")
			}
		}
		if mode == "live" {
			value := config()
			delete(value, "combined_qualification_diagnostics")
			value["qualification_diagnostics"] = true
			if configure(value) == nil {
				t.Fatal("original fixture-only diagnostic flag widened")
			}
		}
	}
	for _, value := range []map[string]any{{"combined_qualification_diagnostics": true}, {"test_only": true, "decision": "ALLOW", "combined_qualification_diagnostics": true}} {
		if configure(value) == nil || activePolicy.Load() != nil {
			t.Fatal("diagnostics became a standalone authorizer")
		}
	}
}
