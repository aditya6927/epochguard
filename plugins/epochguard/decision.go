package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log"
	"sync/atomic"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
)

type Decision string

const (
	Allow       Decision = "ALLOW"
	Reject      Decision = "REJECT"
	Unavailable Decision = "UNAVAILABLE"
)

// DecisionSource borrows the response for this synchronous call only. An
// external verifier must respect ctx cancellation and must not retain pooled
// Bifrost objects. Its errors/reasons are untrusted and never become refusal text.
type DecisionSource interface {
	Decide(context.Context, *schemas.BifrostResponse) (Decision, error)
}

// fixedDecision is a TEST-ONLY source: it checks no evidence or freshness.
// It deliberately ignores both response content and request context.
type fixedDecision Decision

func (d fixedDecision) Decide(context.Context, *schemas.BifrostResponse) (Decision, error) {
	return Decision(d), nil
}

// delayedDecision is a bounded test fixture for observing cache writes while
// the synchronous decision is pending. No client input selects this delay.
type delayedDecision struct {
	decision fixedDecision
	delay    time.Duration
}

func (d delayedDecision) Decide(ctx context.Context, resp *schemas.BifrostResponse) (Decision, error) {
	timer := time.NewTimer(d.delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return Unavailable, ctx.Err()
	case <-timer.C:
		return d.decision.Decide(ctx, resp)
	}
}

type policy struct {
	source       DecisionSource
	cacheNoStore bool
}

// Publication is atomic for concurrent hooks/reconfiguration. A policy and its
// source are immutable; request data is never stored in this process-level slot.
var activePolicy atomic.Pointer[policy]

func configure(config any) error {
	// Even a failed reconfiguration must not leave an earlier ALLOW installed.
	activePolicy.Store(nil)
	var cfg struct {
		TestOnly            bool                    `json:"test_only"`
		Decision            Decision                `json:"decision"`
		CacheNoStore        bool                    `json:"cache_no_store"`
		TestDecisionDelayMS int                     `json:"test_decision_delay_ms"`
		Verifier            *HTTPVerificationConfig `json:"verifier"`
	}
	data, err := json.Marshal(config)
	if err != nil {
		return errors.New("epochguard: invalid decision configuration")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&cfg); err != nil {
		return errors.New("epochguard: invalid decision configuration")
	}
	if cfg.Verifier != nil {
		if cfg.Decision != "" || cfg.TestDecisionDelayMS != 0 || cfg.CacheNoStore {
			return errors.New("epochguard: verifier and test decision configuration cannot be mixed")
		}
		if cfg.TestOnly != (cfg.Verifier.EvidenceMode == "fixture") {
			return errors.New("epochguard: fixture evidence requires explicit test_only configuration")
		}
		source, err := newHTTPDecisionSource(*cfg.Verifier)
		if err != nil {
			return err
		}
		// Cache is disabled in the 003A deployment. Suppress writes as defense
		// in depth if a trusted deployment accidentally enables the built-in.
		activePolicy.Store(&policy{source: source, cacheNoStore: true})
		log.Print("epochguard event=init task=003a source=http policy=python-windows-latest-v1")
		return nil
	}
	if cfg.Decision == "" {
		cfg.Decision = Unavailable
	}
	if cfg.Decision != Allow && cfg.Decision != Reject && cfg.Decision != Unavailable {
		return errors.New("epochguard: unknown decision")
	}
	if cfg.Decision != Unavailable && !cfg.TestOnly {
		return errors.New("epochguard: deterministic decisions require test_only=true")
	}
	if (cfg.CacheNoStore || cfg.TestDecisionDelayMS != 0) && !cfg.TestOnly {
		return errors.New("epochguard: cache qualification requires test_only=true")
	}
	if cfg.TestDecisionDelayMS < 0 || cfg.TestDecisionDelayMS > 2000 {
		return errors.New("epochguard: test decision delay must be between 0 and 2000ms")
	}
	var source DecisionSource = fixedDecision(cfg.Decision)
	if cfg.TestDecisionDelayMS != 0 {
		source = delayedDecision{decision: fixedDecision(cfg.Decision), delay: time.Duration(cfg.TestDecisionDelayMS) * time.Millisecond}
	}
	activePolicy.Store(&policy{source: source, cacheNoStore: cfg.CacheNoStore})
	log.Printf("epochguard event=init task=002b test_only=%t decision=%s", cfg.TestOnly, cfg.Decision)
	return nil
}

func refusal(status int, code, message string) *schemas.BifrostError {
	return &schemas.BifrostError{
		IsBifrostError: true,
		StatusCode:     schemas.Ptr(status),
		AllowFallbacks: schemas.Ptr(false),
		Error: &schemas.ErrorField{
			Type: schemas.Ptr("epochguard_policy_error"), Code: schemas.Ptr(code), Message: message,
		},
	}
}

func enforce(ctx context.Context, resp *schemas.BifrostResponse, upstreamErr *schemas.BifrostError, source DecisionSource) (*schemas.BifrostResponse, *schemas.BifrostError, error) {
	// Preserve the genuine failure, including identity and provider fallback policy.
	// Discard any simultaneous response instead of treating it as a candidate.
	if upstreamErr != nil {
		return nil, upstreamErr, nil
	}
	decision := Unavailable
	if resp != nil && resp.ChatResponse != nil && source != nil && ctx.Err() == nil {
		if result, err := source.Decide(ctx, resp); err == nil && ctx.Err() == nil {
			decision = result
		}
	}
	switch decision {
	case Allow:
		return resp, nil, nil
	case Reject:
		return nil, refusal(403, "epochguard_rejected", "EpochGuard refused the provider response."), nil
	default:
		return nil, refusal(503, "epochguard_verification_unavailable", "EpochGuard verification is unavailable."), nil
	}
}
