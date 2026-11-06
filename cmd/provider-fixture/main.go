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
	flag.Parse()
	if *answerMode != "echo" && *answerMode != "claim" {
		log.Fatal("unsupported fixture answer mode")
	}
	var mu sync.Mutex
	calls := make(map[string]int)
	mux := http.NewServeMux()
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
		mu.Unlock()
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
		writeJSON(w, http.StatusOK, map[string]any{
			"id": "chatcmpl-epochguard-fixture", "object": "chat.completion", "created": 1,
			"model": req.Model,
			"choices": []any{map[string]any{
				"index": 0, "message": map[string]string{"role": "assistant", "content": answer}, "finish_reason": "stop",
			}},
			"usage": map[string]int{"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
		})
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
