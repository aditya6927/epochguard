package main

import (
	"context"
	"errors"
	"log"
	"net"
)

// Contains metadata only, never a wrapped transport error or response body.
type verificationFailure struct {
	category string
	status   int
}

func (verificationFailure) Error() string { return "epochguard: verification unavailable" }

func transportFailure(err error) verificationFailure {
	var timeout net.Error
	switch {
	case errors.Is(err, context.DeadlineExceeded):
		return verificationFailure{category: "verification_timeout"}
	case errors.Is(err, context.Canceled):
		return verificationFailure{category: "verification_cancelled"}
	case errors.As(err, &timeout) && timeout.Timeout():
		return verificationFailure{category: "verification_timeout"}
	default:
		return verificationFailure{category: "request_failure"}
	}
}

func logVerificationFailure(err error) {
	category, status := "verification_unavailable", 0
	var failure verificationFailure
	if errors.As(err, &failure) {
		category, status = failure.category, failure.status
	} else if err != nil {
		category = transportFailure(err).category
	}
	switch category {
	case "request_failure", "verification_timeout", "verification_cancelled", "verifier_http_failure", "invalid_contract", "unsupported_candidate", "verification_unavailable":
	default:
		category = "verification_unavailable"
	}
	if status >= 100 && status <= 599 {
		safeLogf("epochguard event=verification_failure category=%s http_status=%d", category, status)
	} else {
		safeLogf("epochguard event=verification_failure category=%s", category)
	}
}

// A failed sink (including a panicking writer) cannot change enforcement.
// Callers supply fixed formats and allowlisted metadata only.
func safeLogf(format string, args ...any) {
	defer func() { _ = recover() }()
	log.Printf(format, args...)
}
