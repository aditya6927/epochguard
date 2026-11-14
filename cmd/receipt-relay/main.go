// Test-only post-receipt mutation relay. It never receives the signing key.
package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const protectedPath = "/openai/v1/chat/completions"
const receiptHeader = "X-EpochGuard-Internal-Receipt"

func main() {
	if os.Getenv("EPOCHGUARD_TEST_MODE") != "1" {
		log.Fatal("test relay unavailable")
	}
	var mu sync.Mutex
	target, fault := "gateway", "none"
	var savedBody []byte
	var savedReceipt string
	client := &http.Client{Timeout: 10 * time.Second, Transport: &http.Transport{Proxy: nil, DisableCompression: true}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(`{"status":"ok"}`)) })
	mux.HandleFunc("POST /test/control", func(w http.ResponseWriter, r *http.Request) {
		var config struct{ Target, Fault string }
		d := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1024))
		d.DisallowUnknownFields()
		if d.Decode(&config) != nil {
			w.WriteHeader(400)
			return
		}
		if config.Target == "" {
			config.Target = "gateway"
		}
		if config.Fault == "" {
			config.Fault = "none"
		}
		switch config.Target {
		case "gateway", "gateway-control", "gateway-invalid", "gateway-initfail", "gateway-loadfail":
		default:
			w.WriteHeader(400)
			return
		}
		switch config.Fault {
		case "none", "missing", "mac", "body", "status", "replay", "policy", "version", "duplicate", "partial", "stalled", "oversized", "fake":
		default:
			w.WriteHeader(400)
			return
		}
		mu.Lock()
		target, fault = config.Target, config.Fault
		mu.Unlock()
		w.WriteHeader(200)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		selectedTarget, selectedFault := target, fault
		oldBody, oldReceipt := append([]byte(nil), savedBody...), savedReceipt
		mu.Unlock()
		data, err := io.ReadAll(io.LimitReader(r.Body, 65537))
		if err != nil || len(data) > 65536 {
			w.WriteHeader(413)
			return
		}
		req, err := http.NewRequestWithContext(r.Context(), r.Method, "http://"+selectedTarget+":8080"+r.URL.RequestURI(), bytes.NewReader(data))
		if err != nil {
			w.WriteHeader(503)
			return
		}
		req.Header = r.Header.Clone()
		response, err := client.Do(req)
		if err != nil {
			w.WriteHeader(503)
			return
		}
		defer response.Body.Close()
		body, err := io.ReadAll(io.LimitReader(response.Body, 256*1024+1))
		if err != nil {
			w.WriteHeader(503)
			return
		}
		for key, values := range response.Header {
			if !strings.EqualFold(key, "Content-Length") {
				w.Header()[key] = append([]string(nil), values...)
			}
		}
		status := response.StatusCode
		if r.URL.Path == protectedPath {
			receipt := response.Header.Get(receiptHeader)
			if selectedFault == "none" && receipt != "" && status == 200 {
				mu.Lock()
				savedBody, savedReceipt = append([]byte(nil), body...), receipt
				mu.Unlock()
			}
			switch selectedFault {
			case "missing":
				w.Header().Del(receiptHeader)
			case "mac":
				parts := strings.Split(receipt, ".")
				if len(parts) == 2 && len(parts[1]) > 0 {
					first := "A"
					if parts[1][0] == 'A' {
						first = "B"
					}
					w.Header().Set(receiptHeader, parts[0]+"."+first+parts[1][1:])
				}
			case "body":
				body = append(body, ' ')
			case "status":
				status = 201
			case "duplicate":
				w.Header().Add(receiptHeader, receipt)
			case "replay":
				body = oldBody
				w.Header().Set(receiptHeader, oldReceipt)
			case "version", "policy":
				parts := strings.Split(receipt, ".")
				if len(parts) == 2 {
					payload, _ := base64.RawURLEncoding.DecodeString(parts[0])
					var parsed map[string]any
					if json.Unmarshal(payload, &parsed) == nil {
						field := "version"
						if selectedFault == "policy" {
							field = "policy_id"
						}
						parsed[field] = "wrong"
						payload, _ = json.Marshal(parsed)
						w.Header().Set(receiptHeader, base64.RawURLEncoding.EncodeToString(payload)+"."+parts[1])
					}
				}
			case "partial":
				w.Header().Set("Content-Length", "100000")
				w.Header().Set("Connection", "close")
				w.WriteHeader(status)
				_, _ = w.Write(body[:len(body)/2])
				return
			case "stalled":
				w.WriteHeader(status)
				w.(http.Flusher).Flush()
				select {
				case <-r.Context().Done():
				case <-time.After(12 * time.Second):
				}
				return
			case "oversized":
				body = bytes.Repeat([]byte("x"), 256*1024+1)
			case "fake":
				w.Header().Set(receiptHeader, "unsigned")
				w.Header().Set("X-EpochGuard-Plugin", "epochguard")
				w.Header().Set("X-EpochGuard-Verified", "true")
			}
		}
		w.WriteHeader(status)
		_, _ = w.Write(body)
	})
	server := &http.Server{Addr: ":9003", Handler: mux, ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 3 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 15 * time.Second, ErrorLog: log.New(io.Discard, "", 0)}
	log.Print("test receipt relay listening")
	if server.ListenAndServe() != nil {
		log.Fatal("test relay stopped")
	}
}
