package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestBoundReceiptCapturesRequestAndProjectsMetadata(t *testing.T) {
	for _, channel := range []string{"id", "model", "system_fingerprint", "service_tier", "created", "usage", "extra_fields", "routing_info", "headers", "missing-body", "large-body"} {
		t.Run(channel, func(t *testing.T) {
			p := &policy{source: fixedDecision(Allow), attestation: &attestationKey{bytes.Repeat([]byte{7}, 32)}, receiptPolicy: proseSchema + "/" + prosePolicy}
			activePolicy.Store(p)
			defer activePolicy.Store(nil)
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			defer ctx.Cancel()
			original := []byte("{\"model\":\"fixture/epochguard-test\",\"messages\":[{\"role\":\"user\",\"content\":\"private request\"}]}\n")
			req := &schemas.HTTPRequest{Method: "POST", Path: "/openai/v1/chat/completions", Body: append([]byte(nil), original...), Headers: map[string]string{nonceHeader: strings.Repeat("a", 64), "X-EpochGuard-Request-SHA256": strings.Repeat("0", 64)}}
			if channel == "missing-body" {
				req.Body = nil
			}
			if channel == "large-body" {
				req.Body = bytes.Repeat([]byte("x"), 65537)
			}
			record(ctx, "http_pre")
			beginAttestation(ctx, req)
			for i := range req.Body {
				req.Body[i] = 'x'
			} // pooled request is not retained
			candidate := claimCandidate("3.15.2")
			text := *candidate.ChatResponse.Choices[0].Message.Content.ContentStr
			recordAttestation(ctx, p, candidate, nil, candidate, nil)
			body := map[string]any{"object": "chat.completion", "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": text}}}}
			const sentinel = "UNVERIFIED_METADATA_004GS"
			switch channel {
			case "id", "model", "system_fingerprint", "service_tier":
				body[channel] = sentinel
			case "created":
				body[channel] = 123
			case "usage":
				body[channel] = map[string]any{sentinel: map[string]int{"count": 1}}
			case "extra_fields":
				body[channel] = map[string]string{"provider": sentinel, "original_model_requested": sentinel, "resolved_model_used": sentinel}
			case "routing_info":
				body["extra_fields"] = map[string]any{"routing_info": map[string]any{"provider": sentinel, "model": sentinel, "key": sentinel, "is_fallback": false}}
			}
			raw, _ := json.Marshal(body)
			response := &schemas.HTTPResponse{StatusCode: 200, Body: raw, Headers: map[string]string{"Content-Type": "application/json", "X-Provider-Metadata": sentinel}}
			finishAttestation(ctx, response)
			header := response.Headers[receiptHeader]
			if channel == "missing-body" || channel == "large-body" {
				if header != "" {
					t.Fatal("missing request capture signed")
				}
				return
			}
			if header == "" || bytes.Contains(response.Body, []byte(sentinel)) || strings.Contains(response.Headers["X-Provider-Metadata"], sentinel) {
				t.Fatal("untrusted metadata survived projection")
			}
			payload, _ := base64.RawURLEncoding.DecodeString(strings.Split(header, ".")[0])
			var receipt boundEnforcementReceipt
			if json.Unmarshal(payload, &receipt) != nil || receipt.Version != boundReceiptVersion || receipt.RequestSHA256 != shaText(string(original)) || receipt.CandidateSHA256 != shaText(text) || receipt.BodySHA256 != shaText(string(response.Body)) {
				t.Fatal("v2 binding mismatch")
			}
			expected, _ := protectedEntity(&attestationState{outcome: "ALLOW", candidate: text})
			if !bytes.Equal(expected, response.Body) {
				t.Fatal("unexpected projection")
			}
		})
	}
}

func TestBoundProtocolCannotDowngradeConfiguration(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fixture-key")
	if os.WriteFile(path, []byte(strings.Repeat("a", 64)), 0600) != nil {
		t.Fatal("fixture write")
	}
	for _, mode := range []string{multiSchema, proseSchema} {
		for _, protocol := range []string{receiptVersion, boundReceiptVersion} {
			url := "http://verifier/v1/verify/multiclaim"
			if mode == proseSchema {
				url = "http://verifier/v1/verify/prose"
			}
			err := configure(map[string]any{"test_only": true, "verifier": map[string]any{"mode": mode, "url": url, "evidence_mode": "fixture"}, "attestation": map[string]any{"protocol": protocol, "secret_file": path}})
			valid := (mode == multiSchema && protocol == receiptVersion) || (mode == proseSchema && protocol == boundReceiptVersion)
			if (err == nil) != valid {
				t.Fatal("mode/protocol mismatch")
			}
		}
	}
	activePolicy.Store(nil)
}

func TestBoundProviderErrorHasNoUntrustedText(t *testing.T) {
	for _, kind := range []string{"invalid_request_error", "UNVERIFIED_METADATA_004GS"} {
		data, err := protectedEntity(&attestationState{outcome: "PROVIDER_ERROR", kind: kind, code: "UNVERIFIED_METADATA_004GS", message: "UNVERIFIED_METADATA_004GS"})
		if err != nil || bytes.Contains(data, []byte("UNVERIFIED_METADATA_004GS")) || !bytes.Contains(data, []byte("Provider request failed.")) {
			t.Fatal("provider error text released")
		}
	}
}
