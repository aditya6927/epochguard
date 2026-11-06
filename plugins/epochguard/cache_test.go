package main

import (
	"context"
	"testing"
	"time"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/plugins/semanticcache"
)

func TestServerCacheNoStoreOverridesClientFalse(t *testing.T) {
	defer activePolicy.Store(nil)
	if err := Init(map[string]any{"test_only": true, "decision": "REJECT", "cache_no_store": true}); err != nil {
		t.Fatal(err)
	}
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer ctx.Cancel()
	ctx.SetValue(semanticcache.CacheNoStoreKey, false)
	_, stop, err := PreLLMHook(ctx, &schemas.BifrostRequest{RequestType: schemas.ChatCompletionRequest, ChatRequest: &schemas.BifrostChatRequest{}})
	if stop != nil || err != nil || ctx.Value(semanticcache.CacheNoStoreKey) != true {
		t.Fatal("server no-store was overridden")
	}
	if err := configure(map[string]any{"cache_no_store": true}); err == nil {
		t.Fatal("cache qualification requires explicit test configuration")
	}
}

func TestDelayedDecisionRespectsCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	decision, err := (delayedDecision{decision: fixedDecision(Allow), delay: time.Second}).Decide(ctx, candidate())
	if err != context.Canceled || decision != Unavailable {
		t.Fatal("cancelled delayed decision did not fail closed")
	}
	for _, cfg := range []any{
		map[string]any{"test_decision_delay_ms": 1},
		map[string]any{"test_only": true, "test_decision_delay_ms": 2001},
		map[string]any{"test_only": true, "test_decision_delay_ms": -1},
	} {
		if err := configure(cfg); err == nil {
			t.Fatal("unsafe test delay accepted")
		}
	}
}
