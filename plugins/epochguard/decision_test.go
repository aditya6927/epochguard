package main

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"sync"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

type sourceFunc func(context.Context, *schemas.BifrostResponse) (Decision, error)

func (f sourceFunc) Decide(ctx context.Context, resp *schemas.BifrostResponse) (Decision, error) {
	return f(ctx, resp)
}

func candidate() *schemas.BifrostResponse {
	return &schemas.BifrostResponse{ChatResponse: &schemas.BifrostChatResponse{}}
}

func TestEnforceDecisions(t *testing.T) {
	for _, tc := range []struct {
		name   string
		source DecisionSource
		status int
	}{
		{"allow", fixedDecision(Allow), 0},
		{"reject", fixedDecision(Reject), 403},
		{"unavailable", fixedDecision(Unavailable), 503},
		{"unknown", fixedDecision("unexpected"), 503},
		{"missing source", nil, 503},
		{"evaluator error overrides allow", sourceFunc(func(context.Context, *schemas.BifrostResponse) (Decision, error) {
			return Allow, errors.New("PRIVATE_PROVIDER_SENTINEL")
		}), 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			input := candidate()
			resp, refusal, hookErr := enforce(context.Background(), input, nil, tc.source)
			if hookErr != nil {
				t.Fatal(hookErr)
			}
			if tc.status == 0 {
				if resp != input || refusal != nil {
					t.Fatal("ALLOW must preserve pointer identity")
				}
				return
			}
			if resp != nil || refusal == nil || refusal.StatusCode == nil || *refusal.StatusCode != tc.status || refusal.AllowFallbacks == nil || *refusal.AllowFallbacks {
				t.Fatalf("expected terminal refusal %d: resp=%v err=%v", tc.status, resp, refusal)
			}
			data, err := json.Marshal(refusal)
			if err != nil || strings.Contains(string(data), "PRIVATE_PROVIDER_SENTINEL") {
				t.Fatal("unsafe refusal")
			}
		})
	}
}

func TestEnforceMissingResponseAndCancellation(t *testing.T) {
	for _, input := range []*schemas.BifrostResponse{nil, {}} {
		resp, err, _ := enforce(context.Background(), input, nil, fixedDecision(Allow))
		if resp != nil || err == nil || *err.StatusCode != 503 {
			t.Fatal("missing candidate failed open")
		}
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	resp, err, _ := enforce(ctx, candidate(), nil, fixedDecision(Allow))
	if resp != nil || err == nil || *err.StatusCode != 503 {
		t.Fatal("cancelled evaluation failed open")
	}
	ctx, cancel = context.WithCancel(context.Background())
	defer cancel()
	resp, err, _ = enforce(ctx, candidate(), nil, sourceFunc(func(context.Context, *schemas.BifrostResponse) (Decision, error) {
		cancel()
		return Allow, nil
	}))
	if resp != nil || err == nil || *err.StatusCode != 503 {
		t.Fatal("cancellation during evaluation failed open")
	}
}

func TestUpstreamErrorSkipsDecision(t *testing.T) {
	want := &schemas.BifrostError{Error: &schemas.ErrorField{Message: "upstream"}, AllowFallbacks: schemas.Ptr(true)}
	resp, err, hookErr := enforce(context.Background(), candidate(), want, sourceFunc(func(context.Context, *schemas.BifrostResponse) (Decision, error) {
		t.Fatal("provider failure must not be evaluated")
		return Allow, nil
	}))
	if resp != nil || err != want || hookErr != nil || !*want.AllowFallbacks {
		t.Fatal("changed upstream error identity/policy")
	}
}

func TestDecisionCompletesBeforeResponseRelease(t *testing.T) {
	entered, release, done := make(chan struct{}), make(chan struct{}), make(chan struct{})
	go func() {
		defer close(done)
		_, _, _ = enforce(context.Background(), candidate(), nil, sourceFunc(func(context.Context, *schemas.BifrostResponse) (Decision, error) {
			close(entered)
			<-release
			return Allow, nil
		}))
	}()
	<-entered
	select {
	case <-done:
		t.Error("released response before decision")
	default:
	}
	close(release)
	<-done
}

func TestConcurrentHookRequests(t *testing.T) {
	if err := Init(map[string]any{"test_only": true, "decision": "ALLOW"}); err != nil {
		t.Fatal(err)
	}
	defer activePolicy.Store(nil)
	var wg sync.WaitGroup
	for range 16 {
		wg.Go(func() {
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			defer ctx.Cancel()
			_, _ = HTTPTransportPreHook(ctx, &schemas.HTTPRequest{Method: "POST", Path: "/openai/v1/chat/completions", Body: []byte(`{}`)})
			child := schemas.NewBifrostContext(ctx, schemas.NoDeadline)
			defer child.Cancel()
			_ = PreRequestHook(child, nil)
			_, _, _ = PreLLMHook(child, &schemas.BifrostRequest{RequestType: schemas.ChatCompletionRequest, ChatRequest: &schemas.BifrostChatRequest{}})
			input := candidate()
			resp, refusal, err := PostLLMHook(child, input, nil)
			if resp != input || refusal != nil || err != nil {
				t.Error("concurrent ALLOW changed")
			}
			output := &schemas.HTTPResponse{}
			if err := HTTPTransportPostHook(ctx, nil, output); err != nil || output.Headers["X-EpochGuard-Hooks"] != "http_pre,pre_request,pre_llm,post_llm,http_post" {
				t.Error("request trace changed")
			}
		})
	}
	wg.Wait()
}

func TestConfigurationAndExportedPostHook(t *testing.T) {
	defer activePolicy.Store(nil)
	for _, decision := range []Decision{Allow, Reject, Unavailable} {
		if err := Init(map[string]any{"test_only": true, "decision": decision}); err != nil {
			t.Fatal(err)
		}
		ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
		input := candidate()
		resp, refusal, hookErr := PostLLMHook(ctx, input, nil)
		ctx.Cancel()
		if hookErr != nil || (decision == Allow && (resp != input || refusal != nil)) || (decision != Allow && (resp != nil || refusal == nil)) {
			t.Fatalf("exported hook did not enforce %s", decision)
		}
	}
	for _, config := range []any{nil, map[string]any{}, map[string]any{"decision": "UNAVAILABLE"}} {
		if err := Init(config); err != nil {
			t.Fatal(err)
		}
		_, err, _ := enforce(context.Background(), candidate(), nil, activePolicy.Load().source)
		if err == nil || *err.StatusCode != 503 {
			t.Fatal("default must fail closed")
		}
	}
	for _, config := range []any{map[string]any{"decision": "ALLOW"}, map[string]any{"test_only": true, "decision": "typo"}, map[string]any{"test_only": true, "decision": "ALLOW", "header": "bypass"}} {
		if err := configure(config); err == nil || activePolicy.Load() != nil {
			t.Fatal("invalid config was accepted or retained a policy")
		}
		if err := Init(config); err != nil {
			t.Fatal("invalid config must keep the plugin loaded")
		}
		ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
		resp, refusal, hookErr := PostLLMHook(ctx, candidate(), nil)
		ctx.Cancel()
		if resp != nil || refusal == nil || *refusal.StatusCode != 503 || hookErr != nil {
			t.Fatal("invalid config failed open in exported hook")
		}
	}
}
