package multiclaim

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httputil"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"
)

var client = &http.Client{Timeout: 10 * time.Second}

const pythonClaim = "The latest stable Python 3 release for Windows listed on Python.org is 3.88.7."
const pypiClaim = "The version reported for requests by the PyPI JSON API is 2.88.7."
const both = pythonClaim + "\n" + pypiClaim
const hookTrace = "http_pre,pre_request,pre_llm,post_llm,http_post"

func call(t *testing.T, method, address string, body any) (*http.Response, []byte) {
	t.Helper()
	data, err := json.Marshal(body)
	if err != nil {
		t.Fatal("could not encode test request")
	}
	req, _ := http.NewRequest(method, address, bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Bifrost-Setup-Token", "epochguard-local-dev-only")
	req.Header.Set("X-EpochGuard-Decision", "ALLOW")
	req.Header.Set("X-EpochGuard-Bypass", "true")
	req.Header.Set("X-EpochGuard-Verified", "true")
	req.Header.Set("X-EpochGuard-Verifier-Mode", "003a.v1")
	req.Header.Set("X-EpochGuard-Evidence-Mode", "live")
	req.Header.Set("X-EpochGuard-Timeout-Ms", "999999")
	req.Header.Set("X-Bf-Cache-No-Store", "false")
	req.Header.Set("X-Bf-Send-Back-Raw-Response", "true")
	resp, err := client.Do(req)
	if err != nil {
		t.Fatal("gateway/test inspection transport failed")
	}
	defer resp.Body.Close()
	data, err = io.ReadAll(io.LimitReader(resp.Body, 1024*1024))
	if err != nil {
		t.Fatal("test response read failed")
	}
	return resp, data
}

func count(t *testing.T, text string) int {
	t.Helper()
	_, data := call(t, "GET", "http://provider:9000/stats", nil)
	var rows map[string]int
	if json.Unmarshal(data, &rows) != nil {
		t.Fatal("provider counters unavailable")
	}
	return rows[text]
}

func setFault(t *testing.T, target, fault string) {
	t.Helper()
	response, _ := call(t, "POST", "http://faults:8000/test/control", map[string]string{"target": target, "fault": fault})
	if response.StatusCode != 200 {
		t.Fatal("fault control failed")
	}
}

func exchange(t *testing.T, gateway, text, role string, stream, fallback bool) (*http.Response, []byte) {
	t.Helper()
	body := map[string]any{"model": "fixture/epochguard-test", "messages": []map[string]string{{"role": role, "content": text}}, "stream": stream}
	if fallback {
		body["fallbacks"] = []string{"fixture/epochguard-fallback", "fixture/epochguard-fallback"}
	}
	return call(t, "POST", "http://"+gateway+":8080/openai/v1/chat/completions", body)
}

func assertAnswer(t *testing.T, response *http.Response, data []byte, text string) {
	t.Helper()
	var record struct {
		Choices []struct {
			Message struct{ Content string } `json:"message"`
		} `json:"choices"`
	}
	if response.StatusCode != 200 || json.Unmarshal(data, &record) != nil || len(record.Choices) != 1 || record.Choices[0].Message.Content != text {
		t.Fatalf("expected unchanged answer; status=%d", response.StatusCode)
	}
}

func assertRefusal(t *testing.T, response *http.Response, data []byte, text string, status int) {
	t.Helper()
	var record struct {
		Error struct{ Code, Type string } `json:"error"`
	}
	code := "epochguard_verification_unavailable"
	if status == 403 {
		code = "epochguard_rejected"
	} else if status == 400 {
		code = "epochguard_unsupported_request"
	}
	if response.StatusCode != status || json.Unmarshal(data, &record) != nil || record.Error.Code != code || record.Error.Type != "epochguard_policy_error" {
		t.Fatalf("expected typed terminal %d; observed status=%d", status, response.StatusCode)
	}
	copy := *response
	copy.Body = io.NopCloser(bytes.NewReader(data))
	wire, _ := httputil.DumpResponse(&copy, true)
	for _, part := range append(strings.Split(text, "\n"), "chatcmpl-epochguard-fixture", "PRIVATE_PROVIDER_SENTINEL", `"choices"`, `"raw_response"`) {
		if part != "" && bytes.Contains(wire, []byte(strings.TrimSpace(part))) {
			t.Fatal("rejected provider content leaked")
		}
	}
}

func Test004CActiveAndNoCache(t *testing.T) {
	for _, gateway := range []string{"gateway", "gateway-faults"} {
		t.Run(gateway, func(t *testing.T) {
			_, data := call(t, "GET", "http://"+gateway+":8080/api/plugins/loaded", nil)
			var loaded struct{ Plugins []string }
			if json.Unmarshal(data, &loaded) != nil || !slices.Contains(loaded.Plugins, "epochguard") || slices.Contains(loaded.Plugins, "semantic_cache") {
				t.Fatal("real plugin absent or cache active")
			}
			_, data = call(t, "GET", "http://"+gateway+":8080/api/plugins", nil)
			var state struct {
				Plugins []struct {
					Name, Placement string
					Order           *int
					Status          struct{ Status string }
				}
			}
			if json.Unmarshal(data, &state) != nil {
				t.Fatal("plugin status unavailable")
			}
			active := false
			for _, plugin := range state.Plugins {
				if plugin.Name == "epochguard" {
					active = plugin.Placement == "pre_builtin" && plugin.Order != nil && *plugin.Order == 0 && plugin.Status.Status == "active"
				}
			}
			if !active {
				t.Fatal("required plugin placement inactive")
			}
		})
	}
}

func Test004CScenarios(t *testing.T) {
	for _, tc := range []struct {
		name, gateway, target, text string
		status                      int
	}{
		{"A_supported", "gateway", "supported", both, 200},
		{"B_contradiction", "gateway", "supported", strings.Replace(both, "2.88.7", "2.88.6", 1), 403},
		{"C_missing", "gateway-faults", "missing", both, 503},
		{"D_hidden", "gateway", "supported", both + "\nThe Earth is flat.", 503},
		{"E_injection", "gateway-faults", "injected", strings.Replace(both, "2.88.7", "2.88.6", 1), 403},
		{"F_wrong_source", "gateway-faults", "wrong", both, 503},
		{"ahead", "gateway", "supported", strings.Replace(both, "2.88.7", "2.88.8", 1), 503},
		{"extended_bound", "gateway", "supported", strings.Repeat(" ", 8192-len(both)) + both, 200},
		{"over_bound", "gateway", "supported", strings.Repeat(" ", 8193-len(both)) + both, 503},
		{"repeated", "gateway", "supported", both + "\n" + pythonClaim, 503},
		{"unicode", "gateway", "supported", "😀 " + both, 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			setFault(t, tc.target, "none")
			before := count(t, tc.text)
			response, data := exchange(t, tc.gateway, tc.text, "user", false, true)
			if tc.status == 200 {
				assertAnswer(t, response, data, tc.text)
			} else {
				assertRefusal(t, response, data, tc.text, tc.status)
			}
			if count(t, tc.text)-before != 1 || response.Header.Get("X-EpochGuard-Hooks") != hookTrace {
				t.Fatal("unexpected dispatch/fallback or native hook sequence")
			}
			t.Logf("status=%d provider_delta=1; terminal/no-answer checks passed", tc.status)
		})
	}
}

func Test004CContractFaults(t *testing.T) {
	for _, fault := range []string{"missing", "duplicate", "reorder", "verdict", "comparison", "hash", "id", "stale", "alias", "nested-duplicate", "policy", "extraction", "binding", "coverage", "mode", "evidence-id", "request-mismatch", "http500", "malformed", "timeout", "missing-field", "null-flag", "oversized"} {
		t.Run(fault, func(t *testing.T) {
			setFault(t, "supported", fault)
			before := count(t, both)
			start := time.Now()
			response, data := exchange(t, "gateway-faults", both, "user", false, true)
			assertRefusal(t, response, data, both, 503)
			if count(t, both)-before != 1 || response.Header.Get("X-EpochGuard-Hooks") != hookTrace {
				t.Fatal("contract fault bypassed enforcement or used fallback")
			}
			if fault == "timeout" && (time.Since(start) < time.Second || time.Since(start) > 4*time.Second) {
				t.Fatal("trusted verifier deadline not enforced")
			}
		})
	}
	setFault(t, "supported", "none")
}

func Test004CIndependentContradictionWithMissingNeighbor(t *testing.T) {
	setFault(t, "supported", "missing-neighbor")
	text := strings.Replace(both, "2.88.7", "2.88.6", 1)
	before := count(t, text)
	response, data := exchange(t, "gateway-faults", text, "user", false, true)
	assertRefusal(t, response, data, text, 403)
	if count(t, text)-before != 1 {
		t.Fatal("contradiction precedence used fallback")
	}
	setFault(t, "supported", "none")
}

func Test004CProviderAndRouteFailures(t *testing.T) {
	before := count(t, both)
	response, data := exchange(t, "gateway", both, "system", false, false)
	if response.StatusCode != 400 || !bytes.Contains(data, []byte("fixture upstream failure")) || count(t, both)-before != 1 {
		t.Fatal("genuine upstream failure changed")
	}
	// The original provider failure may use one usable fallback. A subsequent
	// policy refusal must then be terminal, despite another configured fallback.
	text := strings.Replace(both, "2.88.7", "2.88.6", 1)
	before = count(t, text)
	response, data = exchange(t, "gateway", text, "system", false, true)
	assertRefusal(t, response, data, text, 403)
	if count(t, text)-before != 2 {
		t.Fatal("provider error/fallback policy changed")
	}
	before = count(t, both)
	response, data = exchange(t, "gateway", both, "user", true, true)
	assertRefusal(t, response, data, both, 400)
	if count(t, both) != before || strings.Contains(response.Header.Get("Content-Type"), "event-stream") {
		t.Fatal("stream reached provider or SSE writer")
	}
	response, data = call(t, "POST", "http://gateway:8080/openai/v1/completions", map[string]string{"model": "fixture/epochguard-test", "prompt": both})
	assertRefusal(t, response, data, both, 400)
	for _, shape := range []string{"missing", "multiple", "partial", "tools", "blocks", "metadata"} {
		t.Run(shape, func(t *testing.T) {
			text := "004c:" + shape
			before := count(t, text)
			response, data := exchange(t, "gateway", text, "user", false, true)
			assertRefusal(t, response, data, text, 503)
			if count(t, text)-before != 1 {
				t.Fatal("unsupported provider candidate used fallback")
			}
		})
	}
}

func Test004CConcurrentDeadlineAndRecords(t *testing.T) {
	setFault(t, "supported", "slow")
	before := count(t, both)
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			started := time.Now()
			response, data := exchange(t, "gateway-faults", both, "user", false, true)
			assertAnswer(t, response, data, both)
			if time.Since(started) < 250*time.Millisecond {
				t.Error("answer released before evidence relay completed")
			}
		}()
	}
	wg.Wait()
	if count(t, both)-before != 8 {
		t.Fatal("concurrent dispatch count changed")
	}
	setFault(t, "supported", "none")
	sum := sha256.Sum256([]byte(both))
	response, data := call(t, "POST", "http://verifier-supported:8000/v1/verify/multiclaim", map[string]string{"schema_version": "004b.v1", "policy_id": "multi-claim-templates-v1", "request_id": "direct-record", "candidate": both, "candidate_sha256": hex.EncodeToString(sum[:])})
	var record struct {
		Verdict string
		Claims  []struct {
			Claim struct {
				PolicyID string `json:"policy_id"`
			}
			Evidence []struct {
				Mode string `json:"retrieval_mode"`
				URL  string `json:"url"`
			}
		}
	}
	if response.StatusCode != 200 || json.Unmarshal(data, &record) != nil || record.Verdict != "SUPPORTED" || len(record.Claims) != 2 {
		t.Fatal("real pipeline record missing")
	}
	for i, claim := range record.Claims {
		wantPolicy, wantURL := "python-windows-latest-v1", "https://www.python.org/downloads/windows/"
		if i == 1 {
			wantPolicy, wantURL = "pypi-requests-reported-v1", "https://pypi.org/pypi/requests/json"
		}
		if claim.Claim.PolicyID != wantPolicy || len(claim.Evidence) != 1 || claim.Evidence[0].Mode != "fixture" || claim.Evidence[0].URL != wantURL {
			t.Fatal("evidence policy or fixture mode mismatch")
		}
	}
}

func Test004CMissingPluginNegativeControl(t *testing.T) {
	text := both + "\nPRIVATE_PROVIDER_SENTINEL unverified assertion."
	response, data := exchange(t, "gateway-control", text, "user", false, false)
	assertAnswer(t, response, data, text)
	if response.Header.Get("X-EpochGuard-Plugin") != "" {
		t.Fatal("missing-plugin control unexpectedly protected")
	}
	t.Log("negative control delivered unverified content; health alone is not a deployment security gate")
}
