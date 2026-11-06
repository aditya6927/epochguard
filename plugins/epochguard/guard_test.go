package main

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestHTTPGuard(t *testing.T) {
	for _, tc := range []struct {
		name, path, body string
		allowed          bool
	}{
		{"buffered", "/openai/v1/chat/completions", `{"stream":false}`, true},
		{"default buffered", "/openai/v1/chat/completions", `{}`, true},
		{"streaming", "/openai/v1/chat/completions", `{"stream":true}`, false},
		{"stream string", "/openai/v1/chat/completions", `{"stream":"true"}`, false},
		{"missing snapshot", "/openai/v1/chat/completions", ``, false},
		{"invalid JSON", "/openai/v1/chat/completions", `{`, false},
		{"null body", "/openai/v1/chat/completions", ` null `, false},
		{"other inference", "/openai/v1/responses", `{}`, false},
		{"native route", "/v1/chat/completions", `{}`, false},
		{"passthrough", "/openai/passthrough", `{}`, false},
		{"health", "/health", ``, true},
		{"management", "/api/plugins", ``, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			req := &schemas.HTTPRequest{Method: "POST", Path: tc.path, Body: []byte(tc.body), Headers: map[string]string{"X-EpochGuard-Decision": "ALLOW"}}
			got := guardHTTP(req)
			if tc.allowed != (got == nil) {
				t.Fatalf("allowed=%t response=%v", tc.allowed, got)
			}
			if got != nil && got.StatusCode != 400 {
				t.Fatal("expected safe 400")
			}
		})
	}
	if guardHTTP(nil) == nil {
		t.Fatal("nil request allowed")
	}
}
