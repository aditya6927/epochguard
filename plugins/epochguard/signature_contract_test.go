package main

import (
	"encoding/json"
	"reflect"
	"testing"

	"github.com/maximhq/bifrost/core/providers/gemini"
	"github.com/maximhq/bifrost/core/schemas"
)

// These fixtures use the real pinned converter. They demonstrate information
// loss; they must never become a signature-eligibility authority.
func signatureConversion(t *testing.T, raw string) *schemas.BifrostResponse {
	t.Helper()
	var response gemini.GenerateContentResponse
	if json.Unmarshal([]byte(raw), &response) != nil {
		t.Fatal("synthetic Gemini envelope invalid")
	}
	return &schemas.BifrostResponse{ChatResponse: response.ToBifrostChatResponse()}
}

const signatureEnvelope = `{"candidates":[{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"synthetic visible answer","thoughtSignature":"c3ludGhldGlj"}]}}]}`

func TestPinnedSignatureRepresentation(t *testing.T) {
	response := signatureConversion(t, signatureEnvelope)
	chat := response.ChatResponse
	if chat.Object != "chat.completion" || len(chat.Choices) != 1 || chat.Choices[0].FinishReason == nil || *chat.Choices[0].FinishReason != "stop" {
		t.Fatal("unexpected native chat envelope")
	}
	message := chat.Choices[0].Message
	if message == nil || message.Role != schemas.ChatMessageRoleAssistant || message.Content == nil || message.Content.ContentStr == nil || *message.Content.ContentStr != "synthetic visible answer" || message.Content.ContentBlocks != nil {
		t.Fatal("native visible text binding changed")
	}
	want := &schemas.ChatAssistantMessage{ReasoningDetails: []schemas.ChatReasoningDetails{{
		Index: 0, Type: schemas.BifrostReasoningDetailsTypeEncrypted, Signature: schemas.Ptr("c3ludGhldGlj"),
	}}}
	if !reflect.DeepEqual(message.ChatAssistantMessage, want) {
		t.Fatal("signature-only typed representation changed; review compatibility")
	}
	if _, stage, err := inspectBufferedCandidate(response); err == nil || stage != "unsupported_provider_annotations" {
		t.Fatal("unreviewed encrypted signature authorized")
	}
}

func TestPinnedSignatureConversionCollisionsFailClosed(t *testing.T) {
	valid := signatureConversion(t, signatureEnvelope)
	for name, raw := range map[string]string{
		"file-data-neighbor":  `{"candidates":[{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"synthetic visible answer","thoughtSignature":"c3ludGhldGlj"},{"fileData":{"mimeType":"image/png","fileUri":"https://example.invalid/synthetic.png"}}]}}]}`,
		"file-data-same-part": `{"candidates":[{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"synthetic visible answer","thoughtSignature":"c3ludGhldGlj","fileData":{"mimeType":"image/png","fileUri":"https://example.invalid/synthetic.png"}}]}}]}`,
		"second-candidate":    `{"candidates":[{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"synthetic visible answer","thoughtSignature":"c3ludGhldGlj"}]}},{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"unaccounted second candidate"}]}}]}`,
		"detached-signature":  `{"candidates":[{"finishReason":"STOP","content":{"role":"model","parts":[{"text":"synthetic visible answer"},{"thoughtSignature":"c3ludGhldGlj"}]}}]}`,
	} {
		t.Run(name, func(t *testing.T) {
			ambiguous := signatureConversion(t, raw)
			if !reflect.DeepEqual(valid, ambiguous) {
				t.Fatal("pinned conversion collision changed; re-audit source contract")
			}
			if _, stage, err := inspectBufferedCandidate(ambiguous); err == nil || stage != "unsupported_provider_annotations" {
				t.Fatal("ambiguous signature conversion admitted")
			}
		})
	}
}
