package main

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/maximhq/bifrost/core/providers/gemini"
	"github.com/maximhq/bifrost/core/schemas"
)

func TestNativeGeminiCandidateDiagnosticsPreserveEligibility(t *testing.T) {
	for index, tc := range []struct{ raw, reason string }{
		{`{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"synthetic exact text"}]}}]}`, "candidate_eligible"},
		{`{"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[{"text":"synthetic exact text"}]}}]}`, "unsupported_finish_reason"},
		{`{"candidates":[]}`, "buffered_candidate_shape"},
		{`{"candidates":[{"finishReason":"STOP"}]}`, "candidate_eligible"},
		{`{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"synthetic exact text","thoughtSignature":"c3ludGhldGlj"}]}}]}`, "unsupported_provider_annotations"},
		{`{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"synthetic thinking","thought":true}]}}]}`, "unsupported_provider_annotations"},
		{`{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"first"},{"text":"second"}]}}]}`, "buffered_candidate_shape"},
	} {
		var native gemini.GenerateContentResponse
		if json.Unmarshal([]byte(tc.raw), &native) != nil {
			t.Fatal("synthetic envelope")
		}
		response := &schemas.BifrostResponse{ChatResponse: native.ToBifrostChatResponse()}
		text, reason, err := inspectBufferedCandidate(response)
		original, originalErr := bufferedCandidate(response)
		if reason != tc.reason || (err == nil) != (reason == "candidate_eligible") || (err == nil) != (originalErr == nil) || text != original {
			t.Fatalf("vector=%d stage=%s expected=%s accepted=%t", index, reason, tc.reason, err == nil)
		}
	}
}

func TestQualificationTracePrivateBoundedAndFailureTolerant(t *testing.T) {
	path := filepath.Join(t.TempDir(), "stages.jsonl")
	sink := &qualificationSink{path: path}
	var wg sync.WaitGroup
	for range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			defer ctx.Cancel()
			ctx.SetValue(hookSequenceKey, &hookTrace{qualification: &qualificationTrace{sink: sink, RequestSHA256: strings.Repeat("a", 64)}})
			qualificationEvent(ctx, "PRIVATE_UNTRUSTED_STAGE")
			for range 32 {
				qualificationEvent(ctx, "unsupported_provider_annotations")
			}
			finishQualification(ctx, 503)
			finishQualification(ctx, 503) // exactly once per exchange
		}()
	}
	wg.Wait()
	data, err := os.ReadFile(path)
	if err != nil || bytes.Contains(data, []byte("PRIVATE")) || len(bytes.Split(bytes.TrimSpace(data), []byte("\n"))) != 32 {
		t.Fatal("diagnostics not bounded/private")
	}
	info, _ := os.Stat(path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("diagnostics file permissions")
	}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer ctx.Cancel()
	ctx.SetValue(hookSequenceKey, &hookTrace{qualification: &qualificationTrace{sink: &qualificationSink{path: filepath.Join(path, "unwritable")}, RequestSHA256: strings.Repeat("a", 64)}})
	finishQualification(ctx, 503) // filesystem failures must remain diagnostic
	allowed, failure, hookErr := enforce(ctx, claimCandidate("3.88.7"), nil, fixedDecision(Allow))
	if allowed == nil || failure != nil || hookErr != nil {
		t.Fatal("failed diagnostic sink changed allowed decision")
	}
	allowed, failure, hookErr = enforce(ctx, claimCandidate("3.88.7"), nil, fixedDecision(Unavailable))
	if allowed != nil || failure == nil || *failure.StatusCode != 503 || *failure.AllowFallbacks || hookErr != nil {
		t.Fatal("failed diagnostic sink weakened terminal refusal")
	}
}

func TestQualificationConfigCannotEnableOrdinaryProfile(t *testing.T) {
	defer activePolicy.Store(nil)
	for _, config := range []map[string]any{
		{"qualification_diagnostics": true},
		{"test_only": true, "qualification_diagnostics": true, "decision": "ALLOW"},
		{"test_only": true, "qualification_diagnostics": true, "verifier": map[string]any{"mode": multiSchema}},
	} {
		if configure(config) == nil || activePolicy.Load() != nil {
			t.Fatal("diagnostics escaped fixture v2 prose boundary")
		}
	}
}
