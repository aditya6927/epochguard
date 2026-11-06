// cache-store-proxy is TEST-ONLY transport instrumentation in front of real
// Redis Stack. It forwards commands/replies unchanged and can hold an HSET
// before forwarding it, making the async-write/delete race reproducible.
// Its unauthenticated controls must remain on the isolated test network.
package main

import (
	"bufio"
	"bytes"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

type observation struct {
	Seen      int    `json:"seen"`
	Forwarded int    `json:"forwarded"`
	Held      bool   `json:"held"`
	Key       string `json:"key"`
}

type gate struct{ release chan struct{} }
type proxy struct {
	mu    sync.Mutex
	gates map[string]*gate
	stats map[string]observation
}

// Only client command frames are decoded. Replies (including RESP3) are copied
// byte-for-byte. Binary bulk strings are length-delimited, never line-scanned.
func readCommand(r *bufio.Reader) ([]byte, []string, error) {
	line, err := r.ReadString('\n')
	if err != nil {
		return nil, nil, err
	}
	if len(line) < 4 || line[0] != '*' || !strings.HasSuffix(line, "\r\n") {
		return nil, nil, errors.New("expected RESP command array")
	}
	n, err := strconv.Atoi(line[1 : len(line)-2])
	if err != nil || n < 1 || n > 10000 {
		return nil, nil, errors.New("invalid command length")
	}
	var raw bytes.Buffer
	raw.WriteString(line)
	args := make([]string, 0, n)
	for range n {
		line, err = r.ReadString('\n')
		if err != nil {
			return nil, nil, err
		}
		if len(line) < 4 || line[0] != '$' || !strings.HasSuffix(line, "\r\n") {
			return nil, nil, errors.New("expected bulk argument")
		}
		size, err := strconv.Atoi(line[1 : len(line)-2])
		if err != nil || size < 0 || size > 4<<20 || raw.Len()+size > 8<<20 {
			return nil, nil, errors.New("argument too large")
		}
		payload := make([]byte, size+2)
		if _, err = io.ReadFull(r, payload); err != nil {
			return nil, nil, err
		}
		if !bytes.HasSuffix(payload, []byte("\r\n")) {
			return nil, nil, errors.New("invalid bulk terminator")
		}
		raw.WriteString(line)
		raw.Write(payload)
		args = append(args, string(payload[:size]))
	}
	return raw.Bytes(), args, nil
}

func cacheScope(args []string) string {
	if len(args) < 4 || !strings.EqualFold(args[0], "HSET") {
		return ""
	}
	for i := 2; i+1 < len(args); i += 2 {
		if args[i] == "cache_key" {
			// The pinned Redis store hex-encodes filterable TAG values.
			decoded, err := hex.DecodeString(args[i+1])
			if err == nil {
				return string(decoded)
			}
		}
	}
	return ""
}

func (p *proxy) forward(client net.Conn) {
	defer client.Close()
	upstream, err := net.DialTimeout("tcp", "redis:6379", 2*time.Second)
	if err != nil {
		return
	}
	defer upstream.Close()
	go func() { _, _ = io.Copy(client, upstream); _ = client.Close() }()
	r := bufio.NewReader(client)
	for {
		raw, args, err := readCommand(r)
		if err != nil {
			return
		}
		scope := cacheScope(args)
		var hold *gate
		if scope != "" {
			p.mu.Lock()
			v := p.stats[scope]
			v.Seen++
			v.Key = args[1]
			hold = p.gates[scope]
			v.Held = hold != nil
			p.stats[scope] = v
			p.mu.Unlock()
		}
		if hold != nil {
			// Below the cache writer's 30s deadline and the configured Redis
			// read timeout. Never leave a test failure holding a socket forever.
			timer := time.NewTimer(8 * time.Second)
			select {
			case <-hold.release:
				timer.Stop()
			case <-timer.C:
				return
			}
		}
		if _, err = upstream.Write(raw); err != nil {
			return
		}
		if scope != "" {
			p.mu.Lock()
			v := p.stats[scope]
			v.Forwarded++
			v.Held = false
			p.stats[scope] = v
			p.mu.Unlock()
		}
	}
}

func (p *proxy) controls() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) })
	mux.HandleFunc("POST /hold", func(w http.ResponseWriter, r *http.Request) {
		scope := r.URL.Query().Get("scope")
		if scope == "" {
			http.Error(w, "scope required", 400)
			return
		}
		p.mu.Lock()
		defer p.mu.Unlock()
		if p.gates[scope] != nil {
			http.Error(w, "already held", 409)
			return
		}
		p.gates[scope] = &gate{release: make(chan struct{})}
		w.WriteHeader(204)
	})
	mux.HandleFunc("POST /release", func(w http.ResponseWriter, r *http.Request) {
		p.mu.Lock()
		defer p.mu.Unlock()
		scope := r.URL.Query().Get("scope")
		if g := p.gates[scope]; g != nil {
			close(g.release)
			delete(p.gates, scope)
		}
		w.WriteHeader(204)
	})
	mux.HandleFunc("GET /state", func(w http.ResponseWriter, r *http.Request) {
		p.mu.Lock()
		v := p.stats[r.URL.Query().Get("scope")]
		p.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(v)
	})
	mux.HandleFunc("GET /entry", func(w http.ResponseWriter, r *http.Request) {
		key := r.URL.Query().Get("key")
		// Read-only inspector, restricted to the single experiment namespace.
		if !strings.HasPrefix(key, "EpochGuard002C:") {
			http.Error(w, "invalid key", 400)
			return
		}
		conn, err := net.DialTimeout("tcp", "redis:6379", time.Second)
		if err != nil {
			http.Error(w, "backend unavailable", 503)
			return
		}
		defer conn.Close()
		_ = conn.SetDeadline(time.Now().Add(2 * time.Second))
		_, err = fmt.Fprintf(conn, "*2\r\n$6\r\nEXISTS\r\n$%d\r\n%s\r\n", len(key), key)
		if err != nil {
			http.Error(w, "backend write failed", 503)
			return
		}
		line, err := bufio.NewReader(conn).ReadString('\n')
		if err != nil || (line != ":0\r\n" && line != ":1\r\n") {
			http.Error(w, "backend read failed", 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]bool{"exists": line == ":1\r\n"})
	})
	return mux
}

func main() {
	p := &proxy{gates: make(map[string]*gate), stats: make(map[string]observation)}
	listener, err := net.Listen("tcp", ":6380")
	if err != nil {
		log.Fatal(err)
	}
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			go p.forward(conn)
		}
	}()
	server := &http.Server{Addr: ":9001", Handler: p.controls(), ReadHeaderTimeout: 3 * time.Second}
	log.Fatal(server.ListenAndServe())
}
