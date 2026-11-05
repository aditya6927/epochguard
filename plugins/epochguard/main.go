// Package main exports the functions resolved by Bifrost's native plugin loader.
// Task 002A observes hook execution; it makes no verification decisions.
package main

import (
	"errors"
	"log"
	"strings"
	"sync"

	"github.com/maximhq/bifrost/core/schemas"
)

const hookSequenceKey schemas.BifrostContextKey = "epochguard.002a.hooks"

// HTTP hooks and core hooks can receive parent/child contexts. Sharing a
// request-owned pointer makes phases recorded in the child visible to HTTP post.
type hookTrace struct {
	mu     sync.Mutex
	phases []string
}

func GetName() string { return "epochguard" }

func Init(_ any) error {
	log.Print("epochguard event=init task=002a")
	return nil
}

func Cleanup() error {
	log.Print("epochguard event=cleanup task=002a")
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

func HTTPTransportPreHook(ctx *schemas.BifrostContext, _ *schemas.HTTPRequest) (*schemas.HTTPResponse, error) {
	record(ctx, "http_pre")
	return nil, nil
}

func PreRequestHook(ctx *schemas.BifrostContext, _ *schemas.BifrostRequest) error {
	record(ctx, "pre_request")
	return nil
}

func PreLLMHook(ctx *schemas.BifrostContext, req *schemas.BifrostRequest) (*schemas.BifrostRequest, *schemas.LLMPluginShortCircuit, error) {
	record(ctx, "pre_llm")
	return req, nil, nil
}

func PostLLMHook(ctx *schemas.BifrostContext, resp *schemas.BifrostResponse, bifrostErr *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError, error) {
	record(ctx, "post_llm")
	return resp, bifrostErr, nil
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
	trace.mu.Unlock()
	resp.Headers["X-EpochGuard-Plugin"] = GetName()
	return nil
}
