package routesurface

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"reflect"
	"slices"
	"strings"
	"testing"
	"time"
)

const answer = "ROUTE_PROVIDER_ANSWER"
const token = "epochguard-local-dev-only" // Public local fixture token only.

type event struct{ Phase, Path, Kind, Code string }

func get(t *testing.T, address string, target any) {
	t.Helper()
	c := http.Client{Timeout: 5 * time.Second}
	r, err := c.Get(address)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	if r.StatusCode != 200 || json.NewDecoder(r.Body).Decode(target) != nil {
		t.Fatal("inspection failed")
	}
}
func count(t *testing.T) int {
	var stats map[string]int
	get(t, "http://provider:9000/stats", &stats)
	total := 0
	for _, n := range stats {
		total += n
	}
	return total
}
func trace(t *testing.T, gateway string) []event {
	var events []event
	get(t, "http://"+gateway+":9010/events", &events)
	return events
}

// The exact origin-form target is written to the socket. No URL parser,
// redirect following or client-side dot-segment normalization is involved.
func raw(t *testing.T, gateway, method, target string, body []byte, auth bool, extra string) (*http.Response, []byte) {
	t.Helper()
	conn, err := net.DialTimeout("tcp", gateway+":8080", 5*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(15 * time.Second))
	headers := ""
	if auth {
		headers = "X-Bifrost-Setup-Token: " + token + "\r\n"
	}
	connection := "close"
	if strings.Contains(extra, "Upgrade: websocket") {
		connection = "Upgrade"
	}
	wire := fmt.Sprintf("%s %s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: %s\r\nX-EpochGuard-Decision: ALLOW\r\nX-EpochGuard-Bypass: true\r\n%s%s\r\n", method, target, gateway, len(body), connection, headers, extra)
	if _, err = io.WriteString(conn, wire); err != nil {
		t.Fatal(err)
	}
	if _, err = conn.Write(body); err != nil {
		t.Fatal(err)
	}
	r, err := http.ReadResponse(bufio.NewReader(conn), &http.Request{Method: method})
	if err != nil {
		t.Fatal(err)
	}
	defer r.Body.Close()
	data, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		t.Fatal(err)
	}
	return r, data
}

func TestLoadedConfiguration(t *testing.T) {
	for _, gateway := range []string{"reject", "control", "warp-reject", "warp-control", "nolog"} {
		t.Run(gateway, func(t *testing.T) {
			r, body := raw(t, gateway, "GET", "/api/plugins/loaded", nil, true, "")
			var loaded struct{ Plugins []string }
			if r.StatusCode != 200 || json.Unmarshal(body, &loaded) != nil {
				t.Fatal("cannot inspect loaded plugins")
			}
			guarded := gateway != "control" && gateway != "warp-control"
			if !slices.Contains(loaded.Plugins, "routeobserver") || slices.Contains(loaded.Plugins, "epochguard") != guarded || slices.Contains(loaded.Plugins, "semantic_cache") {
				t.Fatalf("unexpected loaded plugins: %v", loaded.Plugins)
			}
			r, body = raw(t, gateway, "GET", "/api/plugins", nil, true, "")
			var status struct {
				Plugins []struct {
					Name, Placement string
					Order           *int
					Enabled         bool
					Status          struct{ Status string }
				}
			}
			if r.StatusCode != 200 || json.Unmarshal(body, &status) != nil {
				t.Fatal("cannot inspect plugin status")
			}
			found := false
			for _, p := range status.Plugins {
				if p.Name == "epochguard" {
					found = p.Enabled && p.Placement == "pre_builtin" && p.Order != nil && *p.Order == 0 && p.Status.Status == "active"
				}
			}
			if found != guarded {
				t.Fatal("EpochGuard placement/status changed")
			}
			t.Logf("gateway=%s loaded=%v epochguard_pre_builtin_0=%t", gateway, loaded.Plugins, found)
		})
	}
}

func chat(stream bool, passthrough bool) []byte {
	model := "fixture/epochguard-test"
	if passthrough {
		model = "epochguard-test"
	}
	data, _ := json.Marshal(map[string]any{"model": model, "stream": stream, "messages": []any{map[string]string{"role": "user", "content": "ROUTE_SENTINEL_003C"}}})
	return data
}

func exposed(r *http.Response, body []byte) bool {
	// Inspect headers as well as the entire buffered/SSE body.
	wire := string(body) + fmt.Sprint(r.Header)
	return strings.Contains(wire, answer) || strings.Contains(wire, "chatcmpl-route-audit")
}

func requireEvents(t *testing.T, got, want []event) {
	t.Helper()
	if len(got) == 0 && len(want) == 0 {
		return
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("hook trace: got %+v; want %+v", got, want)
	}
}

func TestRouteMatrix(t *testing.T) {
	cases := []struct {
		target, kind string
		stream       bool
	}{
		{"/openai/v1/chat/completions", "protected", false},
		{"/openai/v1/chat/completions", "guard", true},
		{"/openai_passthrough/v1/chat/completions", "passthrough", false},
		{"/openai_passthrough/v1/chat/completions", "passthrough", true},
		{"/anthropic_passthrough/v1/messages", "passthrough", false},
		{"/anthropic_passthrough/v1/messages", "passthrough", true},
		{"/genai_passthrough/v1/models/test:generateContent", "guard", false},
		{"/azure_passthrough/openai/deployments/test/chat/completions", "guard", false},
		{"/bedrock_passthrough/agent/test/alias/test/session/test/text", "guard", false},
		{"/chatgpt_passthrough/backend-api/codex/responses", "guard", false},
		{"/sagemaker_passthrough/endpoints/test/invocations", "guard", false},
		{"/runware_passthrough/v1", "guard", false},
		{"/v1/chat/completions", "guard", false},
		{"/v1/responses", "guard", false},
		{"/openai/v1/responses", "guard", false},
		{"/v1/async/chat/completions", "unregistered", false},
		{"/openai/v1/passthrough", "unregistered", false},
		{"/openai%2fv1/chat/completions", "redirect", false},
		{"/openai/v1/chat%2fcompletions", "redirect", false},
		{"/openai//v1/chat/completions", "redirect", false},
		{"/openai/v1/chat/completions/", "redirect", false},
		{"/OpenAI/v1/chat/completions", "redirect", false},
		{"/openai/v1/x/../chat/completions", "redirect", false},
		{"/openai/v1/%2e%2e/v1/chat/completions", "redirect", false},
		{"/openai_passthrough/../openai/v1/chat/completions", "mismatch_chat", false},
		{"/openai_passthrough/%2e%2e/api/warp/chat", "mismatch_api", false},
		{"/openai_passthrough//v1/chat/completions", "passthrough", false},
		{"/api/warp/%2e/chat", "redirect", false},
		{"/api//warp/chat", "redirect", false},
	}
	for i, tc := range cases {
		t.Run(fmt.Sprintf("%02d_%s_stream=%t", i, tc.target, tc.stream), func(t *testing.T) {
			for _, gateway := range []string{"reject", "control"} {
				if gateway == "control" && tc.kind == "guard" {
					continue
				}
				before := count(t)
				old := len(trace(t, gateway))
				header := ""
				if !strings.Contains(tc.target, "passthrough") {
					header = "X-Model-Provider: fixture\r\n"
				}
				r, body := raw(t, gateway, "POST", tc.target, chat(tc.stream, strings.Contains(tc.target, "passthrough")), true, header)
				events := trace(t, gateway)[old:]
				delta := count(t) - before
				leak := exposed(r, body)
				t.Logf("gateway=%s sent_target=%q status=%d provider_delta=%d answer_bytes=%t events=%+v location=%q", gateway, tc.target, r.StatusCode, delta, leak, events, r.Header.Get("Location"))
				if gateway == "reject" {
					if leak {
						t.Fatal("confirmed unprotected provider answer")
					}
					if tc.kind == "protected" {
						if r.StatusCode != 403 || delta != 1 {
							t.Fatal("protected route enforcement changed")
						}
					}
					if tc.kind == "guard" || tc.kind == "passthrough" {
						if r.StatusCode != 400 || !bytes.Contains(body, []byte("epochguard_unsupported_request")) || delta != 0 {
							t.Fatalf("guard did not stop dispatch: %s", body)
						}
					}
				} else if tc.kind == "protected" || tc.kind == "passthrough" {
					if r.StatusCode != 200 || delta != 1 || !leak {
						t.Fatalf("negative control unusable: %s", body)
					}
				}
				path := tc.target
				switch tc.kind {
				case "redirect", "unregistered":
					status := 308
					if tc.kind == "unregistered" {
						status = 405
					}
					if r.StatusCode != status || delta != 0 || leak {
						t.Fatal("router-only result changed")
					}
					if status == 308 && r.Header.Get("Location") == "" {
						t.Fatal("missing redirect destination")
					}
					requireEvents(t, events, nil)
				case "mismatch_chat", "mismatch_api":
					path = "/openai/v1/chat/completions"
					if tc.kind == "mismatch_api" {
						path = "/api/warp/chat"
					}
					if r.StatusCode != 404 || delta != 0 || leak {
						t.Fatal("passthrough prefix validation changed")
					}
					requireEvents(t, events, []event{{Phase: "http_pre", Path: path}})
				default:
					if strings.Contains(path, "passthrough//") {
						path = strings.Replace(path, "//", "/", 1)
					}
					want := []event{{Phase: "http_pre", Path: path}}
					if tc.kind == "protected" || (tc.kind == "passthrough" && gateway == "control") {
						kind, code := "chat_completion", ""
						if tc.kind == "passthrough" {
							kind = "passthrough"
							if tc.stream {
								kind = "passthrough_stream"
							}
						}
						if gateway == "reject" {
							code = "epochguard_rejected"
						}
						want = append(want, event{Phase: "pre_request", Kind: kind}, event{Phase: "pre_llm", Kind: kind}, event{Phase: "post_llm", Code: code})
						if tc.stream {
							want = append(want, event{Phase: "post_llm"})
						}
					}
					requireEvents(t, events, want)
				}
			}
		})
	}
}

func TestWarpBoundary(t *testing.T) {
	for _, gateway := range []string{"reject", "control", "nolog", "warp-reject", "warp-control"} {
		for _, stream := range []bool{false, true} {
			t.Run(fmt.Sprintf("%s_stream=%t", gateway, stream), func(t *testing.T) {
				body, _ := json.Marshal(map[string]any{"stream": stream, "messages": []any{map[string]string{"role": "user", "content": "ROUTE_SENTINEL_WARP"}}})
				before := count(t)
				old := len(trace(t, gateway))
				r, data := raw(t, gateway, "POST", "/api/warp/chat", body, true, "")
				events := trace(t, gateway)[old:]
				delta := count(t) - before
				leak := exposed(r, data)
				t.Logf("gateway=%s stream=%t status=%d provider_delta=%d answer_bytes=%t events=%+v body=%s", gateway, stream, r.StatusCode, delta, leak, events, data)
				for _, e := range events {
					if e.Phase == "http_pre" {
						t.Fatal("unexpected transport hook on API route")
					}
				}
				if gateway == "warp-control" {
					if r.StatusCode != 200 || delta != 1 || !leak {
						t.Fatal("Warp no-plugin control did not execute/expose the synthetic model")
					}
				} else if leak || delta != 0 {
					t.Fatal("Warp dispatched or exposed an unqualified model response")
				}
				if strings.HasPrefix(gateway, "warp-") {
					code := ""
					if gateway == "warp-reject" {
						code = "epochguard_unsupported_request"
						if r.StatusCode != 200 || !bytes.Contains(data, []byte("EpochGuard supports buffered chat completions only.")) || !bytes.Contains(data, []byte("upstream_error")) {
							t.Fatal("Warp refusal wrapping changed")
						}
					}
					requireEvents(t, events, []event{{Phase: "pre_request", Kind: "responses_stream"}, {Phase: "pre_llm", Kind: "responses_stream"}, {Phase: "post_llm", Code: code}})
				} else {
					if r.StatusCode != 503 || !bytes.Contains(data, []byte("no_log_store")) {
						t.Fatal("Warp prerequisite refusal changed")
					}
					requireEvents(t, events, nil)
				}
			})
		}
	}
}

func TestManagementAndAsyncControls(t *testing.T) {
	for _, tc := range []struct {
		method, target, headers string
		auth                    bool
		status                  int
	}{
		{"GET", "/health", "", false, 200}, {"GET", "/api/plugins/loaded", "", true, 200}, {"GET", "/api/plugins/loaded", "", false, 401},
		{"POST", "/openai/v1/chat/completions", "X-Bf-Async: true\r\nX-Model-Provider: fixture\r\n", false, 400},
		{"POST", "/openai/v1/chat/completions", "X-Bf-Async-Id: test\r\nX-Model-Provider: fixture\r\n", false, 400},
		{"GET", "/v1/responses", "Upgrade: websocket\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n", false, 400},
		{"GET", "/v1/realtime", "Upgrade: websocket\r\n", false, 400},
		{"GET", "/v1/live/sessions", "Upgrade: websocket\r\n", false, 400},
		{"POST", "/v1/live/sessions", "", false, 400},
		{"POST", "/relay/test/v1/chat/completions", "", false, 400},
	} {
		t.Run(tc.method+tc.target+tc.headers, func(t *testing.T) {
			before := count(t)
			old := len(trace(t, "reject"))
			r, body := raw(t, "reject", tc.method, tc.target, chat(false, false), tc.auth, tc.headers)
			delta := count(t) - before
			t.Logf("target=%q auth=%t status=%d provider_delta=%d events=%+v", tc.target, tc.auth, r.StatusCode, delta, trace(t, "reject")[old:])
			if r.StatusCode != tc.status || delta != 0 || exposed(r, body) {
				t.Fatal("unexpected provider execution")
			}
			want := []event(nil)
			if tc.status == 400 {
				want = []event{{Phase: "http_pre", Path: tc.target}}
				if !bytes.Contains(body, []byte("epochguard_unsupported_request")) {
					t.Fatal("not an EpochGuard refusal")
				}
			}
			requireEvents(t, trace(t, "reject")[old:], want)
		})
	}
}
