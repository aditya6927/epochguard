package main

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestAttestationRequiresExecutedDecisionAndUnchangedBody(t *testing.T) {
	key := &attestationKey{bytes.Repeat([]byte{7}, 32)}
	p := &policy{source: fixedDecision(Allow), attestation: key}
	for _, mode := range []string{"valid", "no-decision", "body", "disabled", "reconfigured", "nonce", "status", "extra", "duplicate", "raw"} {
		t.Run(mode, func(t *testing.T) {
			activePolicy.Store(p)
			defer activePolicy.Store(nil)
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			defer ctx.Cancel()
			nonce := strings.Repeat("a", 64)
			if mode == "nonce" {
				nonce = "forged"
			}
			req := &schemas.HTTPRequest{Method: "POST", Path: "/openai/v1/chat/completions", Headers: map[string]string{nonceHeader: nonce}}
			record(ctx, "http_pre")
			beginAttestation(ctx, req)
			candidate := claimCandidate("3.88.7")
			text := *candidate.ChatResponse.Choices[0].Message.Content.ContentStr
			if mode != "no-decision" {
				recordAttestation(ctx, p, candidate, nil, candidate, nil)
			}
			body, _ := json.Marshal(map[string]any{"object": "chat.completion", "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": text}}}})
			if mode == "body" {
				body = bytes.Replace(body, []byte("3.88.7"), []byte("3.88.6"), 1)
			}
			if mode == "extra" {
				body = bytes.Replace(body, []byte(`"object":`), []byte(`"unchecked":"PRIVATE","object":`), 1)
			}
			if mode == "duplicate" {
				body = bytes.Replace(body, []byte(`"object":`), []byte(`"object":"chat.completion","object":`), 1)
			}
			if mode == "raw" {
				body = bytes.Replace(body, []byte(`"object":`), []byte(`"extra_fields":{"raw_response":"PRIVATE"},"object":`), 1)
			}
			resp := &schemas.HTTPResponse{StatusCode: 200, Body: body, Headers: map[string]string{"Content-Type": "application/json"}}
			if mode == "disabled" {
				activePolicy.Store(nil)
			}
			if mode == "reconfigured" {
				activePolicy.Store(&policy{source: fixedDecision(Allow), attestation: key})
			}
			if mode == "status" {
				resp.StatusCode = 201
			}
			finishAttestation(ctx, resp)
			header := resp.Headers[receiptHeader]
			if (header != "") != (mode == "valid") {
				t.Fatal("receipt issued outside validated decision/body boundary")
			}
			if header != "" {
				parts := strings.Split(header, ".")
				payload, _ := base64.RawURLEncoding.DecodeString(parts[0])
				signature, _ := base64.RawURLEncoding.DecodeString(parts[1])
				mac := hmac.New(sha256.New, key.secret)
				_, _ = mac.Write(payload)
				if !hmac.Equal(signature, mac.Sum(nil)) {
					t.Fatal("invalid signer MAC")
				}
				var receipt enforcementReceipt
				if json.Unmarshal(payload, &receipt) != nil || receipt.BodySHA256 != shaText(string(body)) || receipt.Nonce != nonce || receipt.Outcome != "ALLOW" {
					t.Fatal("receipt binding missing")
				}
			}
		})
	}
}

func TestAttestationSecretAndConfiguration(t *testing.T) {
	path := filepath.Join(t.TempDir(), "key")
	for _, value := range []string{"", "short", strings.Repeat("a", 63), strings.Repeat("g", 64), strings.Repeat("a", 100)} {
		if os.WriteFile(path, []byte(value), 0600) != nil {
			t.Fatal("fixture write failed")
		}
		if _, err := loadAttestation(attestationConfig{receiptVersion, path}); err == nil {
			t.Fatal("invalid key accepted")
		}
	}
	_ = os.WriteFile(path, []byte(strings.Repeat("a", 64)), 0600)
	if _, err := loadAttestation(attestationConfig{receiptVersion, path}); err != nil {
		t.Fatal("valid key refused")
	}
	for _, config := range []any{map[string]any{"test_only": true, "decision": "ALLOW", "attestation": map[string]any{"protocol": receiptVersion, "secret_file": path}}, map[string]any{"verifier": map[string]any{"url": "http://verifier/v1/verify"}, "attestation": map[string]any{"protocol": receiptVersion, "secret_file": path}}} {
		if configure(config) == nil || activePolicy.Load() != nil {
			t.Fatal("attestation enabled outside explicit multi-claim verifier")
		}
	}
}
