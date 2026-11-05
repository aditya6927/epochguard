package main

import (
	"context"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

// A post-hook must preserve upstream errors instead of turning them into success.
func TestPostLLMHookPreservesError(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer ctx.Cancel()
	upstreamErr := &schemas.BifrostError{Error: &schemas.ErrorField{Message: "fixture error"}}
	resp, gotErr, hookErr := PostLLMHook(ctx, nil, upstreamErr)
	if resp != nil || gotErr != upstreamErr || hookErr != nil {
		t.Fatalf("post-hook changed the upstream failure: resp=%v err=%v hookErr=%v", resp, gotErr, hookErr)
	}
}

func TestHookTraceSurvivesCoreChildContext(t *testing.T) {
	transport := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer transport.Cancel()
	_, _ = HTTPTransportPreHook(transport, nil)
	core := schemas.NewBifrostContext(transport, schemas.NoDeadline)
	defer core.Cancel()
	_ = PreRequestHook(core, nil)
	_, _, _ = PreLLMHook(core, &schemas.BifrostRequest{})
	_, _, _ = PostLLMHook(core, &schemas.BifrostResponse{}, nil)
	resp := &schemas.HTTPResponse{}
	_ = HTTPTransportPostHook(transport, nil, resp)
	if got := resp.Headers["X-EpochGuard-Hooks"]; got != "http_pre,pre_request,pre_llm,post_llm,http_post" {
		t.Fatalf("core child phases did not reach transport parent: %q", got)
	}
}

func TestHTTPTransportPostHookNilResponse(t *testing.T) {
	ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
	defer ctx.Cancel()

	// The diagnostic hook must not panic when a response is absent.
	if err := HTTPTransportPostHook(ctx, nil, nil); err == nil {
		t.Fatal("expected an error for nil HTTP response")
	}
}
