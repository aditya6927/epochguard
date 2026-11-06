package main

import (
	"encoding/json"
	"net/http"
	"strings"

	"github.com/maximhq/bifrost/core/schemas"
)

// guardHTTP refuses unsupported traffic before the router can install an SSE
// writer or dispatch a provider call. Health and management remain available;
// they are trusted deployment controls, not protected inference routes.
func guardHTTP(req *schemas.HTTPRequest) *schemas.HTTPResponse {
	if req != nil {
		if req.Path == "/health" || req.Path == "/api" || strings.HasPrefix(req.Path, "/api/") {
			return nil
		}
		if req.Method == http.MethodPost && req.Path == "/openai/v1/chat/completions" && req.CaseInsensitiveHeaderLookup("x-bf-async") == "" && req.CaseInsensitiveHeaderLookup("x-bf-async-id") == "" {
			var body *struct {
				Stream bool `json:"stream"`
			}
			// A missing body (including a skipped large-payload snapshot) cannot
			// prove buffered mode. Let no such request proceed unchecked.
			if json.Unmarshal(req.Body, &body) == nil && body != nil && !body.Stream {
				return nil
			}
		}
	}
	err := refusal(400, "epochguard_unsupported_request", "EpochGuard supports buffered chat completions only.")
	// Only constant, plugin-owned fields are serialized; no provider data exists.
	body, _ := json.Marshal(err)
	return &schemas.HTTPResponse{
		StatusCode: 400,
		Headers:    map[string]string{"Content-Type": "application/json"},
		Body:       body,
	}
}
