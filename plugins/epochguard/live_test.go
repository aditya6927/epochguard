package main

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestLiveProfileConfigurationAndRemainingBudget(t *testing.T) {
	cfg := HTTPVerificationConfig{Mode: multiSchema, URL: "http://verifier/v1/verify/multiclaim", EvidenceMode: "live", TimeoutMS: 30000, TimeoutProfile: "004e-live"}
	source, err := newMultiDecisionSource(cfg)
	if err != nil || !source.liveBudget || source.client.Timeout != 30*time.Second {
		t.Fatal("live profile not configured")
	}
	for _, mode := range []string{"unknown", "fixture", "short", "negative", "excessive"} {
		bad := cfg
		switch mode {
		case "unknown":
			bad.TimeoutProfile = "unknown"
		case "fixture":
			bad.EvidenceMode = "fixture"
		case "short":
			bad.TimeoutMS = 5000
		case "negative":
			bad.TimeoutMS = -1
		case "excessive":
			bad.TimeoutMS = 30001
		}
		if _, err := newMultiDecisionSource(bad); err == nil {
			t.Fatal("inconsistent profile accepted")
		}
	}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer ctx.Cancel()
	ctx.SetValue(hookSequenceKey, &hookTrace{started: time.Now().Add(-41 * time.Second)})
	if decision, err := source.Decide(ctx, claimCandidate("3.88.7")); decision != Unavailable || err == nil {
		t.Fatal("elapsed execution budget authorized a candidate")
	}
	if decision, err := source.Decide(context.Background(), claimCandidate("3.88.7")); decision != Unavailable || err == nil {
		t.Fatal("missing request start authorized a candidate")
	}
}

func TestLiveRejectsFixtureEvidence(t *testing.T) {
	v := multiFixture(t, "A")
	req := verificationRequest{multiSchema, multiPolicy, v.RequestID, v.Candidate, v.CandidateSHA256}
	if decision, err := validateMulti(req, v, "live", v.CheckedAt, v.CheckedAt); decision != Unavailable || err == nil {
		t.Fatal("fixture evidence authorized live verification")
	}
}
