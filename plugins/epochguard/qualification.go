package main

import (
	"context"
	"encoding/json"
	"os"
	"sync"

	"github.com/maximhq/bifrost/core/schemas"
)

const qualificationFile = "/tmp/epochguard-005cr.jsonl"

// Qualification-only private tmpfs output, never a client header or log line.
// Holds fixed enums and a request digest only; no Bifrost object is retained.
type qualificationSink struct {
	path string
}

// Serialize append bounds even across overlapping trusted reconfigurations.
var qualificationWriteMu sync.Mutex

type qualificationTrace struct {
	sink          *qualificationSink
	RequestSHA256 string   `json:"request_sha256"`
	Stages        []string `json:"stages"`
	emitted       bool
}

func qualificationEvent(ctx context.Context, stage string) {
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return
	}
	switch stage {
	case "provider_bifrost_failure", "provider_failure", "invalid_chat_response", "buffered_candidate_shape", "unsupported_finish_reason", "unsupported_provider_annotations", "candidate_eligible", "verifier_request_attempted", "verifier_request_completed", "verifier_transport_failure", "verifier_body_failure", "evidence_policy_validation_refused", "evidence_policy_validated", "request_cancelled", "source_unavailable":
	default:
		return
	}
	trace.mu.Lock()
	defer trace.mu.Unlock()
	q := trace.qualification
	if q != nil && len(q.Stages) < 16 {
		q.Stages = append(q.Stages, stage)
	}
}

func finishQualification(ctx *schemas.BifrostContext, status int) {
	// Diagnostic failures, including filesystem errors, cannot alter release.
	defer func() { _ = recover() }()
	trace, _ := ctx.Value(hookSequenceKey).(*hookTrace)
	if trace == nil {
		return
	}
	trace.mu.Lock()
	q := trace.qualification
	if q == nil || q.emitted {
		trace.mu.Unlock()
		return
	}
	q.emitted = true
	copy := *q
	copy.Stages = append([]string(nil), q.Stages...)
	trace.mu.Unlock()
	if status < 100 || status > 599 || !digestRE.MatchString(copy.RequestSHA256) {
		return
	}
	data, err := json.Marshal(struct {
		SchemaVersion string `json:"schema_version"`
		qualificationTrace
		HTTPStatus int `json:"http_status"`
	}{"005cr.go-stages.v1", copy, status})
	if err != nil || len(data) > 2048 {
		return
	}
	qualificationWriteMu.Lock()
	defer qualificationWriteMu.Unlock()
	f, err := os.OpenFile(copy.sink.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || info.Size()+int64(len(data)+1) > 64*1024 {
		return
	}
	_, _ = f.Write(append(data, '\n'))
}
