package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

type transportFunc func(*http.Request) (*http.Response, error)

func (f transportFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

type failedBody struct{}

func (failedBody) Read([]byte) (int, error) { return 0, context.DeadlineExceeded }
func (failedBody) Close() error             { return nil }

func captureLog(t *testing.T) *bytes.Buffer {
	t.Helper()
	old := log.Writer()
	var output bytes.Buffer
	log.SetOutput(&output)
	t.Cleanup(func() { log.SetOutput(old) })
	return &output
}

func TestHTTPFailureDiagnostics(t *testing.T) {
	for _, tc := range []struct {
		mode, category string
		status         int
	}{
		{"transport", "request_failure", 0},
		{"timeout", "verification_timeout", 0},
		{"cancel", "verification_cancelled", 0},
		{"http401", "verifier_http_failure", 401},
		{"http429", "verifier_http_failure", 429},
		{"http503", "verifier_http_failure", 503},
		{"json", "invalid_contract", 200},
		{"media", "invalid_contract", 200},
		{"record", "invalid_contract", 200},
		{"read_timeout", "verification_timeout", 200},
	} {
		t.Run(tc.mode, func(t *testing.T) {
			output := captureLog(t)
			source, _ := newHTTPDecisionSource(HTTPVerificationConfig{URL: "http://verifier/v1/verify"})
			source.client.Transport = transportFunc(func(r *http.Request) (*http.Response, error) {
				switch tc.mode {
				case "transport":
					return nil, errors.New("PRIVATE_SECRET\nevent=forged")
				case "timeout":
					return nil, context.DeadlineExceeded
				case "cancel":
					return nil, context.Canceled
				}
				body := "PRIVATE_SECRET"
				if tc.mode == "record" {
					body = `{"verdict":"PRIVATE_SECRET"}`
				}
				response := &http.Response{StatusCode: tc.status, Header: http.Header{"Content-Type": {"application/json"}}, Body: io.NopCloser(strings.NewReader(body))}
				if tc.mode == "media" {
					response.Header.Set("Content-Type", "PRIVATE_SECRET")
				}
				if tc.mode == "read_timeout" {
					response.Body = failedBody{}
				}
				return response, nil
			})
			candidate := claimCandidate("3.88.7")
			resp, refusal, hookErr := enforce(context.Background(), candidate, nil, source)
			if resp != nil || refusal == nil || *refusal.StatusCode != 503 || *refusal.AllowFallbacks || hookErr != nil {
				t.Fatal("diagnostics changed terminal refusal")
			}
			line := output.String()
			if !strings.Contains(line, "event=verification_failure category="+tc.category) || strings.Count(line, "event=") != 1 {
				t.Fatalf("unexpected diagnostic: %s", line)
			}
			if tc.status != 0 && !strings.Contains(line, "http_status="+strconv.Itoa(tc.status)) {
				t.Fatal("available HTTP status lost")
			}
			if len(line) > 200 || strings.Contains(line, "PRIVATE_SECRET") || strings.Contains(line, "Python") || strings.Contains(line, "3.88.7") || strings.Contains(line, "verifier/v1") {
				t.Fatal("unsafe or unbounded diagnostic")
			}
		})
	}
}

func TestDiagnosticAllowlistAndOtherUnavailable(t *testing.T) {
	for _, err := range []error{nil, errors.New("PRIVATE_SECRET"), verificationFailure{category: "PRIVATE_SECRET", status: 999}} {
		output := captureLog(t)
		source := sourceFunc(func(context.Context, *schemas.BifrostResponse) (Decision, error) { return Unavailable, err })
		resp, refusal, _ := enforce(context.Background(), candidate(), nil, source)
		if resp != nil || refusal == nil || *refusal.StatusCode != 503 {
			t.Fatal("unavailable failed open")
		}
		if strings.Contains(output.String(), "PRIVATE_SECRET") || strings.Contains(output.String(), "999") {
			t.Fatal("untrusted diagnostic fields escaped")
		}
	}
}

type failedLogWriter struct{ panic bool }

func (w failedLogWriter) Write([]byte) (int, error) {
	if w.panic {
		panic("PRIVATE_LOG_ERROR")
	}
	return 0, errors.New("PRIVATE_LOG_ERROR")
}

func TestLoggingFailureCannotChangeEnforcement(t *testing.T) {
	old := log.Writer()
	defer log.SetOutput(old)
	for _, panics := range []bool{false, true} {
		log.SetOutput(failedLogWriter{panic: panics})
		for _, decision := range []Decision{Allow, Reject, Unavailable} {
			if err := configure(map[string]any{"test_only": true, "decision": decision}); err != nil {
				t.Fatal(err)
			}
			ctx := schemas.NewBifrostContext(context.Background(), schemas.NoDeadline)
			input := candidate()
			resp, refusal, hookErr := PostLLMHook(ctx, input, nil)
			ctx.Cancel()
			if hookErr != nil || (decision == Allow && (resp != input || refusal != nil)) || (decision != Allow && (resp != nil || refusal == nil)) {
				t.Fatal("failed log sink changed enforcement")
			}
		}
	}
	activePolicy.Store(nil)
}
