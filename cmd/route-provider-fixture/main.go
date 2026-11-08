// Isolated route-audit provider: synthetic bytes and request-target counters only.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
)

func main() {
	var mu sync.Mutex
	calls := map[string]int{}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) })
	mux.HandleFunc("GET /stats", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		_ = json.NewEncoder(w).Encode(calls)
	})
	mux.HandleFunc("GET /v1/models", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"object": "list", "data": []any{map[string]string{"id": "epochguard-test", "object": "model"}, map[string]string{"id": "epochguard-embed", "object": "model"}}})
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		data, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
		var request map[string]any
		_ = json.Unmarshal(data, &request)
		mu.Lock()
		calls[r.URL.Path]++
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		answer := "ROUTE_PROVIDER_ANSWER"
		if r.URL.Path == "/v1/embeddings" {
			_ = json.NewEncoder(w).Encode(map[string]any{"object": "list", "data": []any{map[string]any{"object": "embedding", "index": 0, "embedding": []float64{1}}}, "model": "epochguard-embed", "usage": map[string]int{"prompt_tokens": 1, "total_tokens": 1}})
			return
		}
		if r.URL.Path == "/v1/responses" {
			response := map[string]any{"id": "resp_route_audit", "object": "response", "created_at": 1, "status": "completed", "model": "epochguard-test", "output": []any{map[string]any{"id": "msg_audit", "type": "message", "role": "assistant", "status": "completed", "content": []any{map[string]string{"type": "output_text", "text": answer}}}}, "usage": map[string]int{"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
			if request["stream"] == true {
				w.Header().Set("Content-Type", "text/event-stream")
				e, _ := json.Marshal(map[string]any{"type": "response.completed", "response": response})
				fmt.Fprintf(w, "event: response.completed\ndata: %s\n\n", e)
				return
			}
			_ = json.NewEncoder(w).Encode(response)
			return
		}
		if request["stream"] == true {
			w.Header().Set("Content-Type", "text/event-stream")
			fmt.Fprintf(w, "data: {\"id\":\"chatcmpl-route-audit\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"index\":0,\"delta\":{\"content\":%q},\"finish_reason\":null}]}\n\ndata: [DONE]\n\n", answer)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "chatcmpl-route-audit", "object": "chat.completion", "created": 1, "model": "epochguard-test", "choices": []any{map[string]any{"index": 0, "message": map[string]string{"role": "assistant", "content": answer}, "finish_reason": "stop"}}, "usage": map[string]int{"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
	})
	if err := http.ListenAndServe(":9000", mux); err != nil {
		panic(err)
	}
}
