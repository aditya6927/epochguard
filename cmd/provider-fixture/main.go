// provider-fixture is a local test double for the upstream HTTP provider only.
// Bifrost and its plugin loader remain real processes in the smoke test.
package main

import (
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"sync"
	"time"
)

func main() {
	answerMode := flag.String("answer-mode", "echo", "local fixture output: echo or claim")
	qualification := flag.Bool("qualification-004c", false, "enable isolated 004C provider-shape controls")
	securityQualification := flag.Bool("qualification-004gs", false, "enable private 004G-S metadata controls")
	flag.Parse()
	if *answerMode != "echo" && *answerMode != "claim" {
		log.Fatal("unsupported fixture answer mode")
	}
	var mu sync.Mutex
	calls := make(map[string]int)
	metadataChannel := "none"
	mux := http.NewServeMux()
	if *securityQualification {
		mux.HandleFunc("POST /test/control", func(w http.ResponseWriter, r *http.Request) {
			var value struct {
				Channel string `json:"channel"`
			}
			d := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1024))
			d.DisallowUnknownFields()
			if d.Decode(&value) != nil {
				w.WriteHeader(400)
				return
			}
			switch value.Channel {
			case "none", "id", "model", "system_fingerprint", "service_tier", "usage", "extra_fields", "routing_info", "nested", "http-header", "raw_response", "annotations", "provider-error":
			default:
				w.WriteHeader(400)
				return
			}
			mu.Lock()
			metadataChannel = value.Channel
			mu.Unlock()
			writeJSON(w, 200, map[string]bool{"fixture": true})
		})
	}
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("GET /stats", func(w http.ResponseWriter, _ *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		writeJSON(w, http.StatusOK, calls)
	})
	mux.HandleFunc("GET /v1/models", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"object": "list",
			"data":   []any{map[string]any{"id": "epochguard-test", "object": "model", "owned_by": "fixture"}},
		})
	})
	mux.HandleFunc("POST /v1/chat/completions", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Model    string `json:"model"`
			Stream   bool   `json:"stream"`
			Messages []struct {
				Role    string `json:"role"`
				Content string `json:"content"`
			} `json:"messages"`
		}
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil || len(req.Messages) != 1 || (req.Model != "epochguard-test" && req.Model != "epochguard-fallback") {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": map[string]string{"message": "unexpected fixture request", "type": "invalid_request_error"}})
			return
		}
		prompt := req.Messages[0].Content
		mu.Lock()
		calls[prompt]++
		channel := metadataChannel
		mu.Unlock()
		sentinel := "UNVERIFIED_METADATA_004GS_" + channel + " The Moon is cheese."
		if channel == "provider-error" {
			writeJSON(w, 400, map[string]any{"error": map[string]string{"type": "invalid_request_error", "message": sentinel, "code": sentinel}})
			return
		}
		if req.Model == "epochguard-test" && req.Messages[0].Role == "system" {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": map[string]string{"message": "fixture upstream failure", "type": "invalid_request_error"}})
			return
		}
		if req.Stream {
			// The control gateway can deliver real sentinel SSE bytes. A protected
			// streaming request must never reach this branch (counter stays zero).
			w.Header().Set("Content-Type", "text/event-stream")
			chunk, _ := json.Marshal(map[string]any{
				"id": "chatcmpl-epochguard-fixture", "object": "chat.completion.chunk", "created": 1, "model": req.Model,
				"choices": []any{map[string]any{"index": 0, "delta": map[string]string{"role": "assistant", "content": "fixture: " + prompt}, "finish_reason": nil}},
			})
			_, _ = w.Write(append(append([]byte("data: "), chunk...), []byte("\n\ndata: [DONE]\n\n")...))
			return
		}
		answer := "fixture: " + prompt
		if *answerMode == "claim" {
			// Trusted process configuration for 003A: emit the supplied test
			// candidate verbatim. The real verifier, not this fixture, decides.
			answer = prompt
		}
		result := map[string]any{
			"id": "chatcmpl-epochguard-fixture", "object": "chat.completion", "created": 1,
			"model": req.Model,
			"choices": []any{map[string]any{
				"index": 0, "message": map[string]string{"role": "assistant", "content": answer}, "finish_reason": "stop",
			}},
			"usage": map[string]int{"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
		}
		if *qualification {
			choices := result["choices"].([]any)
			choice := choices[0].(map[string]any)
			switch prompt {
			case "004c:missing":
				result["choices"] = []any{}
			case "004c:multiple":
				result["choices"] = append(choices, choices[0])
			case "004c:partial":
				choice["finish_reason"] = "length"
			case "004c:tools":
				choice["message"] = map[string]any{"role": "assistant", "content": answer, "tool_calls": []any{map[string]any{"id": "fixture-tool", "type": "function", "function": map[string]string{"name": "untrusted", "arguments": "{}"}}}}
			case "004c:blocks":
				choice["message"] = map[string]any{"role": "assistant", "content": []any{map[string]string{"type": "text", "text": answer}}}
			case "004c:metadata":
				choice["content_filter_results"] = map[string]any{"untrusted": true}
			}
		}
		switch channel {
		case "id", "model", "system_fingerprint", "service_tier":
			result[channel] = sentinel
		case "usage":
			result["usage"].(map[string]int)[sentinel] = 1
		case "extra_fields":
			result["extra_fields"] = map[string]any{"provider": sentinel, "original_model_requested": sentinel, "resolved_model_used": sentinel}
		case "routing_info":
			result["extra_fields"] = map[string]any{"routing_info": map[string]any{"provider": sentinel, "model": sentinel, "key": sentinel, "requested_model": sentinel}}
		case "nested":
			result["metadata"] = map[string]any{"nested": map[string]string{"text": sentinel}}
		case "raw_response":
			result["extra_fields"] = map[string]string{"raw_response": sentinel}
		case "annotations":
			result["choices"].([]any)[0].(map[string]any)["message"] = map[string]any{"role": "assistant", "content": answer, "annotations": []any{map[string]string{"text": sentinel}}}
		case "http-header":
			w.Header().Set("X-Provider-Metadata", sentinel)
		}
		writeJSON(w, http.StatusOK, result)
	})
	server := &http.Server{Addr: ":9000", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Print("provider fixture listening on :9000")
	log.Fatal(server.ListenAndServe())
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(value); err != nil {
		log.Printf("write response: %v", err)
	}
}
