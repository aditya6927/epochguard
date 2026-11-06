// Package main exports the functions resolved by Bifrost's native plugin loader.
// Buffered chat enforcement supports test decisions and the narrow 003A verifier.
package main

import (
	"errors"
	"log"
	"strings"
	"sync"

	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/plugins/semanticcache"
)

const hookSequenceKey schemas.BifrostContextKey = "epochguard.002a.hooks"

// HTTP hooks and core hooks can receive parent/child contexts. Sharing a
// request-owned pointer makes phases recorded in the child visible to HTTP post.
type hookTrace struct {
	mu          sync.Mutex
	phases      []string
	cacheAtPost string
}

func GetName() string { return "epochguard" }

func Init(config any) error {
	if err := configure(config); err != nil {
		// Returning an Init error would make the loader omit this plugin.
		// Keep hooks installed with no source: successful candidates fail closed.
		log.Printf("epochguard event=config_invalid decision=UNAVAILABLE error=%v", err)
	}
	return nil
}

func Cleanup() error {
	activePolicy.Store(nil)
	log.Print("epochguard event=cleanup task=002b")
	return nil
}

// record keeps diagnostics on the request context, never in shared global state.
// The scoped context belongs to Bifrost and is not retained after the hook.
func record(ctx *schemas.BifrostContext, phase string) {
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		trace = &hookTrace{}
		ctx.SetValue(hookSequenceKey, trace)
	}
	trace.mu.Lock()
	trace.phases = append(trace.phases, phase)
	trace.mu.Unlock()
	log.Printf("epochguard hook=%s request_id=%v", phase, ctx.Value(schemas.BifrostContextKeyRequestID))
}

func HTTPTransportPreHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest) (*schemas.HTTPResponse, error) {
	record(ctx, "http_pre")
	return guardHTTP(req), nil
}

func PreRequestHook(ctx *schemas.BifrostContext, _ *schemas.BifrostRequest) error {
	record(ctx, "pre_request")
	return nil
}

func PreLLMHook(ctx *schemas.BifrostContext, req *schemas.BifrostRequest) (*schemas.BifrostRequest, *schemas.LLMPluginShortCircuit, error) {
	record(ctx, "pre_llm")
	if policy := activePolicy.Load(); policy != nil && policy.cacheNoStore {
		// Set the actual public key before cache lookup/post-processing. The
		// transport has already parsed client headers; false cannot override us.
		ctx.SetValue(semanticcache.CacheNoStoreKey, true)
	}
	if req == nil || req.RequestType != schemas.ChatCompletionRequest || req.ChatRequest == nil {
		return req, &schemas.LLMPluginShortCircuit{Error: refusal(400, "epochguard_unsupported_request", "EpochGuard supports buffered chat completions only.")}, nil
	}
	return req, nil, nil
}

func PostLLMHook(ctx *schemas.BifrostContext, resp *schemas.BifrostResponse, bifrostErr *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError, error) {
	record(ctx, "post_llm")
	cacheState := "none"
	if resp != nil && resp.GetExtraFields() != nil && resp.GetExtraFields().CacheDebug != nil {
		cacheState = "miss"
		if resp.GetExtraFields().CacheDebug.CacheHit {
			cacheState = "hit"
		}
	}
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace != nil {
		trace.mu.Lock()
		trace.cacheAtPost = cacheState
		trace.mu.Unlock()
	}
	log.Printf("epochguard cache_at_post=%s request_id=%v", cacheState, ctx.Value(schemas.BifrostContextKeyRequestID))
	var source DecisionSource
	if policy := activePolicy.Load(); policy != nil {
		source = policy.source
	}
	return enforce(ctx, resp, bifrostErr, source)
}

// These headers prove execution on this response; they do not certify freshness.
func HTTPTransportPostHook(ctx *schemas.BifrostContext, _ *schemas.HTTPRequest, resp *schemas.HTTPResponse) error {
	// An ordinary HTTP post-hook error is diagnostic, not a client refusal.
	// Avoid panicking if a future transport path supplies no response.
	if resp == nil {
		return errors.New("epochguard: HTTP post-hook received nil response")
	}
	record(ctx, "http_post")
	if resp.Headers == nil {
		resp.Headers = make(map[string]string)
	}
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return errors.New("epochguard: HTTP post-hook missing trace")
	}
	trace.mu.Lock()
	resp.Headers["X-EpochGuard-Hooks"] = strings.Join(trace.phases, ",")
	if trace.cacheAtPost != "" {
		resp.Headers["X-EpochGuard-Cache-At-Post"] = trace.cacheAtPost
	}
	trace.mu.Unlock()
	resp.Headers["X-EpochGuard-Plugin"] = GetName()
	return nil
}
