package protectedingress

import (
	"bytes"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"
)

const both = "The latest stable Python 3 release for Windows listed on Python.org is 3.88.7.\nThe version reported for requests by the PyPI JSON API is 2.88.7."
const route = "/openai/v1/chat/completions"

var client = &http.Client{Timeout: 12 * time.Second, Transport: &http.Transport{Proxy: nil, DisableCompression: true}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}

func call(t *testing.T, method, address string, value any) (*http.Response, []byte) {
	t.Helper()
	data, _ := json.Marshal(value)
	req, _ := http.NewRequest(method, address, bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Bifrost-Setup-Token", "epochguard-local-dev-only")
	// Spoofed and duplicate client internal headers must be stripped, not merged.
	req.Header.Add("X-EpochGuard-Internal-Nonce", strings.Repeat("a", 64))
	req.Header.Add("x-epochguard-internal-nonce", strings.Repeat("b", 64))
	req.Header.Set("X-EpochGuard-Internal-Receipt", "forged")
	req.Header.Set("X-EpochGuard-Verified", "true")
	req.Header.Set("X-Bf-Send-Back-Raw-Response", "true")
	resp, err := client.Do(req)
	if err != nil {
		t.Fatal("test transport unavailable")
	}
	defer resp.Body.Close()
	data, err = io.ReadAll(io.LimitReader(resp.Body, 1024*1024))
	if err != nil {
		t.Fatal("response read failed")
	}
	return resp, data
}
func payload(text, role string, fallback bool) map[string]any {
	v := map[string]any{"model": "fixture/epochguard-test", "messages": []map[string]string{{"role": role, "content": text}}, "stream": false}
	if fallback {
		v["fallbacks"] = []string{"fixture/epochguard-fallback", "fixture/epochguard-fallback"}
	}
	return v
}
func infer(t *testing.T, host, text, role string, fallback bool) (*http.Response, []byte) {
	return call(t, "POST", "http://"+host+":8082"+route, payload(text, role, fallback))
}
func cleanHeaders(t *testing.T, r *http.Response) {
	t.Helper()
	for key := range r.Header {
		if strings.HasPrefix(strings.ToLower(key), "x-epochguard-") {
			t.Fatal("internal receipt/diagnostic header exposed")
		}
	}
}
func allowed(t *testing.T, r *http.Response, data []byte, text string) {
	t.Helper()
	var v struct {
		Choices []struct{ Message struct{ Content string } }
	}
	if r.StatusCode != 200 || json.Unmarshal(data, &v) != nil || len(v.Choices) != 1 || v.Choices[0].Message.Content != text {
		t.Fatalf("expected unchanged authenticated response; status=%d", r.StatusCode)
	}
	cleanHeaders(t, r)
}
func refused(t *testing.T, r *http.Response, data []byte, text string, status int) {
	t.Helper()
	if r.StatusCode != status {
		t.Fatalf("expected refusal %d; status=%d", status, r.StatusCode)
	}
	for _, part := range append(strings.Split(text, "\n"), `"choices"`, `"raw_response"`, "PRIVATE_PROVIDER_SENTINEL", "chatcmpl-epochguard-fixture") {
		if part != "" && bytes.Contains(data, []byte(part)) {
			t.Fatal("unchecked answer leaked")
		}
	}
	cleanHeaders(t, r)
}
func control(t *testing.T, target, fault string) {
	t.Helper()
	r, _ := call(t, "POST", "http://receipt-relay:9003/test/control", map[string]string{"target": target, "fault": fault})
	if r.StatusCode != 200 {
		t.Fatal("private fault control unavailable")
	}
}
func sourceControl(t *testing.T, target, fault string) {
	t.Helper()
	r, _ := call(t, "POST", "http://faults:8000/test/control", map[string]string{"target": target, "fault": fault})
	if r.StatusCode != 200 {
		t.Fatal("private source control unavailable")
	}
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

func TestClientBaseline(t *testing.T) {
	for _, tc := range []struct {
		name, text string
		status     int
	}{{"supported", both, 200}, {"contradicted", strings.Replace(both, "2.88.7", "2.88.6", 1), 403}, {"uncovered", both + "\nPRIVATE_PROVIDER_SENTINEL unverified assertion.", 503}} {
		t.Run(tc.name, func(t *testing.T) {
			r, data := infer(t, "ingress", tc.text, "user", true)
			if tc.status == 200 {
				allowed(t, r, data, tc.text)
			} else {
				refused(t, r, data, tc.text, tc.status)
			}
		})
	}
	r, _ := call(t, "GET", "http://ingress:8082/ready", nil)
	if r.StatusCode != 200 {
		t.Fatal("authenticated management-and-probe readiness failed")
	}
}
func TestClientMissingPluginAndWrongKey(t *testing.T) {
	for _, host := range []string{"ingress-unsafe", "ingress-badkey", "ingress-unavailable"} {
		t.Run(host, func(t *testing.T) {
			r, data := infer(t, host, both, "user", false)
			refused(t, r, data, both, 503)
			r, _ = call(t, "GET", "http://"+host+":8082/ready", nil)
			if r.StatusCode != 503 {
				t.Fatal("unsafe deployment reported ready")
			}
		})
	}
}
func TestClientNetworkBoundary(t *testing.T) {
	for _, host := range []string{"gateway:8080", "provider:9000", "verifier-supported:8000", "receipt-relay:9003", "faults:8000", "10.77.14.10:8080"} {
		t.Run(host, func(t *testing.T) {
			conn, err := net.DialTimeout("tcp", host, 350*time.Millisecond)
			if err == nil {
				conn.Close()
				t.Fatal("client reached private service")
			}
		})
	}
}
func TestClientUnsupportedTraffic(t *testing.T) {
	for _, target := range []string{"/api/plugins", "/v1/chat/completions", route + "/", route + "?x=1", "/openai/v1/%63hat/completions", "//openai/v1/chat/completions"} {
		r, data := call(t, "POST", "http://ingress:8082"+target, payload(both, "user", false))
		refused(t, r, data, both, 400)
	}
	for _, mode := range []string{"get", "stream", "async", "tools", "type", "large"} {
		t.Run(mode, func(t *testing.T) {
			value := payload(both, "user", false)
			method := "POST"
			if mode == "get" {
				method = "GET"
			}
			if mode == "stream" {
				value["stream"] = true
			}
			if mode == "tools" {
				value["tools"] = []any{}
			}
			if mode == "large" {
				value = payload(strings.Repeat("x", 70000), "user", false)
			}
			data, _ := json.Marshal(value)
			req, _ := http.NewRequest(method, "http://ingress:8082"+route, bytes.NewReader(data))
			req.Header.Set("Content-Type", "application/json")
			if mode == "async" {
				req.Header.Set("X-Bf-Async", "true")
			}
			if mode == "type" {
				req.Header.Set("Content-Type", "text/plain")
			}
			r, err := client.Do(req)
			if err != nil {
				t.Fatal("test transport failed")
			}
			defer r.Body.Close()
			body, _ := io.ReadAll(r.Body)
			status := 400
			if mode == "large" {
				status = 413
			}
			refused(t, r, body, both, status)
		})
	}
}

func TestOperatorReceiptAttacks(t *testing.T) {
	control(t, "gateway", "none")
	r, data := infer(t, "ingress-faults", both, "user", false)
	allowed(t, r, data, both)
	defer control(t, "gateway", "none")
	for _, fault := range []string{"missing", "mac", "body", "status", "replay", "policy", "version", "duplicate", "partial", "stalled", "oversized", "fake"} {
		t.Run(fault, func(t *testing.T) {
			control(t, "gateway", fault)
			r, data := infer(t, "ingress-faults", both, "user", true)
			refused(t, r, data, both, 503)
		})
	}
	control(t, "gateway", "replay")
	var wg sync.WaitGroup
	for i := 0; i < 6; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r, data := infer(t, "ingress-faults", both, "user", false)
			refused(t, r, data, both, 503)
		}()
	}
	wg.Wait()
}
func TestOperatorFailureControls(t *testing.T) {
	defer control(t, "gateway", "none")
	for _, target := range []string{"gateway-control", "gateway-invalid", "gateway-initfail", "gateway-loadfail"} {
		t.Run(target, func(t *testing.T) {
			control(t, target, "none")
			r, data := infer(t, "ingress-faults", both, "user", true)
			refused(t, r, data, both, 503)
			r, _ = call(t, "GET", "http://ingress-faults:8082/ready", nil)
			if r.StatusCode != 503 {
				t.Fatal("failed plugin reported ready")
			}
		})
	}
	text := both + "\nPRIVATE_PROVIDER_SENTINEL unverified assertion."
	r, data := call(t, "POST", "http://gateway-control:8080"+route, payload(text, "user", false))
	if r.StatusCode != 200 || !bytes.Contains(data, []byte("PRIVATE_PROVIDER_SENTINEL")) {
		t.Fatal("unsafe direct control did not demonstrate missing-plugin gap")
	}
	t.Log("private no-plugin gateway delivers unchecked content; every client ingress refused it")
}
func TestOperatorVerifierFailures(t *testing.T) {
	defer sourceControl(t, "supported", "none")
	for _, tc := range []struct{ target, fault string }{{"missing", "none"}, {"supported", "http500"}, {"supported", "timeout"}} {
		t.Run(tc.target+"-"+tc.fault, func(t *testing.T) {
			sourceControl(t, tc.target, tc.fault)
			before := count(t, both)
			r, data := infer(t, "ingress", both, "user", true)
			refused(t, r, data, both, 503)
			if !bytes.Contains(data, []byte("epochguard_verification_unavailable")) {
				t.Fatal("authenticated unavailable outcome not preserved")
			}
			if count(t, both)-before != 1 {
				t.Fatal("verifier failure retried/fell back")
			}
		})
	}
}
func TestOperatorProviderErrors(t *testing.T) {
	before := count(t, both)
	r, data := infer(t, "ingress", both, "system", false)
	if r.StatusCode != 400 || !bytes.Contains(data, []byte("fixture upstream failure")) || count(t, both)-before != 1 {
		t.Fatalf("authenticated provider failure not preserved; status=%d", r.StatusCode)
	}
	cleanHeaders(t, r)
	text := strings.Replace(both, "2.88.7", "2.88.6", 1)
	before = count(t, text)
	r, data = infer(t, "ingress", text, "system", true)
	refused(t, r, data, text, 403)
	if count(t, text)-before != 2 {
		t.Fatal("provider fallback or terminal policy semantics changed")
	}
}
func TestOperatorDisable(t *testing.T) {
	r, data := infer(t, "ingress", both, "user", false)
	allowed(t, r, data, both)
	sourceControl(t, "supported", "slow")
	defer sourceControl(t, "supported", "none")
	var inFlight sync.WaitGroup
	for i := 0; i < 4; i++ {
		inFlight.Add(1)
		go func() {
			defer inFlight.Done()
			response, body := infer(t, "ingress", both, "user", false)
			if response.StatusCode == 200 {
				allowed(t, response, body, both)
			} else {
				refused(t, response, body, both, 503)
			}
		}()
	}
	time.Sleep(50 * time.Millisecond)
	r, _ = call(t, "PUT", "http://gateway:8080/api/plugins/epochguard", map[string]any{"enabled": false})
	if r.StatusCode != 200 {
		t.Fatal("trusted runtime disable failed")
	}
	inFlight.Wait()
	text := both + "\nPRIVATE_PROVIDER_SENTINEL unchecked after disable."
	r, data = call(t, "POST", "http://gateway:8080"+route, payload(text, "user", false))
	if r.StatusCode != 200 || !bytes.Contains(data, []byte("PRIVATE_PROVIDER_SENTINEL")) {
		t.Fatal("runtime removal control did not expose underlying unchecked behavior")
	}
	r, data = infer(t, "ingress", text, "user", true)
	refused(t, r, data, text, 503)
	r, _ = call(t, "GET", "http://ingress:8082/ready", nil)
	if r.StatusCode != 503 {
		t.Fatal("stale readiness after disable")
	}
}

func TestClientStartupOffline(t *testing.T) {
	r, data := infer(t, "ingress", both, "user", false)
	refused(t, r, data, both, 503)
	r, _ = call(t, "GET", "http://ingress:8082/ready", nil)
	if r.StatusCode != 503 {
		t.Fatal("ingress ready before gateway")
	}
}
func TestClientRecovery(t *testing.T) {
	deadline := time.Now().Add(40 * time.Second)
	for time.Now().Before(deadline) {
		r, _ := call(t, "GET", "http://ingress:8082/ready", nil)
		if r.StatusCode == 200 {
			r, data := infer(t, "ingress", both, "user", false)
			allowed(t, r, data, both)
			return
		}
		time.Sleep(250 * time.Millisecond)
	}
	t.Fatal("protected deployment did not recover")
}
func TestClientRestartWindow(t *testing.T) {
	deadline := time.Now().Add(30 * time.Second)
	supported, unavailable, recovered := 0, 0, false
	var mu sync.Mutex
	var wg sync.WaitGroup
	for worker := 0; worker < 4; worker++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for time.Now().Before(deadline) {
				r, data := infer(t, "ingress", both, "user", false)
				if r.StatusCode == 200 {
					allowed(t, r, data, both)
					mu.Lock()
					supported++
					if unavailable > 0 {
						recovered = true
					}
					mu.Unlock()
				} else {
					refused(t, r, data, both, 503)
					mu.Lock()
					unavailable++
					mu.Unlock()
				}
				time.Sleep(100 * time.Millisecond)
			}
		}()
	}
	wg.Wait()
	r, data := infer(t, "ingress", both, "user", false)
	allowed(t, r, data, both)
	if supported == 0 || unavailable == 0 || !recovered {
		t.Fatal("restart did not exercise supported/refused/recovered states")
	}
	t.Logf("restart observations: supported=%d safe_refusals=%d recovered=%t", supported, unavailable, recovered)
}
