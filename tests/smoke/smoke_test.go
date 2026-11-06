package smoke

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"slices"
	"strings"
	"testing"
	"time"
)

const expectedHooks = "http_pre,pre_request,pre_llm,post_llm,http_post"

var client = &http.Client{Timeout: 15 * time.Second}

func endpoint(t *testing.T, name string) string {
	t.Helper()
	value := os.Getenv(name)
	if value == "" {
		t.Fatalf("%s must be set; run this integration test through Docker Compose", name)
	}
	return value
}

func getJSON(t *testing.T, url string, target any) {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(url, "/api/") {
		req.Header.Set("X-Bifrost-Setup-Token", endpoint(t, "EPOCHGUARD_SETUP_TOKEN"))
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET %s returned %d", url, resp.StatusCode)
	}
	if err := json.NewDecoder(resp.Body).Decode(target); err != nil {
		t.Fatal(err)
	}
}

func TestLoadedPlugin(t *testing.T) {
	assertLoadedPlugin(t, endpoint(t, "EPOCHGUARD_GATEWAY_URL"))
}

func assertLoadedPlugin(t *testing.T, gateway string) {
	t.Helper()
	var loaded struct {
		Plugins []string `json:"plugins"`
	}
	getJSON(t, gateway+"/api/plugins/loaded", &loaded)
	// This endpoint sorts names alphabetically; it is not the execution order.
	if !slices.Contains(loaded.Plugins, "epochguard") {
		t.Fatalf("EpochGuard is not loaded; got %v", loaded.Plugins)
	}
	var status struct {
		Plugins []struct {
			Name      string `json:"name"`
			Placement string `json:"placement"`
			Order     *int   `json:"order"`
			Enabled   bool   `json:"enabled"`
			Status    struct {
				Status string `json:"status"`
			} `json:"status"`
		} `json:"plugins"`
	}
	getJSON(t, gateway+"/api/plugins", &status)
	for _, p := range status.Plugins {
		if p.Name == "epochguard" {
			if !p.Enabled || p.Placement != "pre_builtin" || p.Order == nil || *p.Order != 0 || p.Status.Status != "active" {
				t.Fatalf("plugin is not active with required placement: %+v", p)
			}
			t.Logf("plugin active; placement=%s order=%d loaded_names=%v", p.Placement, *p.Order, loaded.Plugins)
			return
		}
	}
	t.Fatal("epochguard missing from plugin status")
}

func request(t *testing.T, gateway, role string) (*http.Response, []byte) {
	t.Helper()
	prompt := fmt.Sprintf("%s-%d", t.Name(), time.Now().UnixNano())
	body, err := json.Marshal(map[string]any{
		"model": "fixture/epochguard-test", "stream": false,
		"messages": []map[string]string{{"role": role, "content": prompt}},
	})
	if err != nil {
		t.Fatal(err)
	}
	req, err := http.NewRequest(http.MethodPost, gateway+"/openai/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	// A client-provided diagnostic must not count as proof of execution.
	req.Header.Set("X-EpochGuard-Hooks", "forged-by-client")
	resp, err := client.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	if role == "user" {
		var answer struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		}
		if resp.StatusCode != http.StatusOK || json.Unmarshal(data, &answer) != nil || len(answer.Choices) != 1 || answer.Choices[0].Message.Content != "fixture: "+prompt {
			t.Fatalf("unexpected provider response: status=%d body=%s", resp.StatusCode, data)
		}
	}
	var stats map[string]int
	getJSON(t, endpoint(t, "EPOCHGUARD_PROVIDER_URL")+"/stats", &stats)
	if stats[prompt] != 1 {
		t.Fatalf("expected one real upstream request for %q, got %d", prompt, stats[prompt])
	}
	return resp, data
}

func executionProof(resp *http.Response) error {
	if resp.Header.Get("X-EpochGuard-Plugin") != "epochguard" || resp.Header.Get("X-EpochGuard-Hooks") != expectedHooks {
		return fmt.Errorf("missing EpochGuard execution proof: plugin=%q hooks=%q", resp.Header.Get("X-EpochGuard-Plugin"), resp.Header.Get("X-EpochGuard-Hooks"))
	}
	return nil
}

func TestRealProviderRequest(t *testing.T) {
	resp, _ := request(t, endpoint(t, "EPOCHGUARD_GATEWAY_URL"), "user")
	if err := executionProof(resp); err != nil {
		t.Fatal(err)
	}
	t.Logf("real provider round trip; hooks=%s", resp.Header.Get("X-EpochGuard-Hooks"))
}

func TestUpstreamErrorPreserved(t *testing.T) {
	resp, body := request(t, endpoint(t, "EPOCHGUARD_GATEWAY_URL"), "system")
	if resp.StatusCode != http.StatusBadRequest || !strings.Contains(string(body), "fixture upstream failure") {
		t.Fatalf("upstream error was changed into an unexpected result: status=%d body=%s", resp.StatusCode, body)
	}
	if err := executionProof(resp); err != nil {
		t.Fatal(err)
	}
}

func TestConcurrentRequestContexts(t *testing.T) {
	for i := 0; i < 6; i++ {
		t.Run(fmt.Sprintf("request-%d", i), func(t *testing.T) {
			t.Parallel()
			resp, _ := request(t, endpoint(t, "EPOCHGUARD_GATEWAY_URL"), "user")
			if err := executionProof(resp); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestHealthyGatewayWithoutPluginFailsProof(t *testing.T) {
	control := endpoint(t, "EPOCHGUARD_CONTROL_URL")
	var health map[string]any
	getJSON(t, control+"/health", &health)
	resp, _ := request(t, control, "user")
	if err := executionProof(resp); err == nil {
		t.Fatal("execution check accepted a healthy gateway without EpochGuard")
	} else {
		t.Logf("negative control correctly rejected: %v", err)
	}
}
