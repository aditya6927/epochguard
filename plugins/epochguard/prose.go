package main

import (
	"errors"
	"fmt"
	"net/url"
	"reflect"
	"regexp"
	"strings"
	"time"
)

const proseSchema = "004g.v1"
const prosePolicy = "bounded-prose-v1"

type proseMapping struct {
	ClaimID    string `json:"claim_id"`
	SourceText string `json:"source_text"`
	Start      int    `json:"start"`
	End        int    `json:"end"`
	PolicyID   string `json:"policy_id"`
	Version    string `json:"version"`
	Canonical  string `json:"canonical"`
}
type proseResult struct {
	SchemaVersion   string         `json:"schema_version"`
	PolicyID        string         `json:"policy_id"`
	RequestID       string         `json:"request_id"`
	Candidate       string         `json:"candidate"`
	CandidateSHA256 string         `json:"candidate_sha256"`
	Coverage        string         `json:"coverage"`
	ReasonCode      string         `json:"reason_code"`
	Mappings        []proseMapping `json:"mappings"`
	Verification    *multiResult   `json:"verification"`
}

// Independently authored closed registry. No model or Python parsing is invoked.
var proseForms = []struct {
	policy  string
	pattern *regexp.Regexp
}{
	{verificationPolicy, pythonSentence}, {pypiPolicy, pypiSentence},
	{verificationPolicy, regexp.MustCompile(`^Python\.org currently lists Python (` + versionPattern + `) as its latest stable Windows release\.`)},
	{verificationPolicy, regexp.MustCompile(`^Python\.org lists Python (` + versionPattern + `) as its latest stable Windows release\.`)},
	{verificationPolicy, regexp.MustCompile(`^Python\.org lists (` + versionPattern + `) as the latest stable Windows release\.`)},
	{verificationPolicy, regexp.MustCompile(`^Python\.org lists Python (` + versionPattern + `) as its latest stable release for Windows\.`)},
	{pypiPolicy, regexp.MustCompile(`^PyPI reports requests version (` + numericVersion.String()[1:len(numericVersion.String())-1] + `)\.`)},
	{pypiPolicy, regexp.MustCompile(`^The PyPI JSON API reports requests version (` + numericVersion.String()[1:len(numericVersion.String())-1] + `)\.`)},
	{pypiPolicy, regexp.MustCompile(`^According to the PyPI JSON API, the version of requests is (` + numericVersion.String()[1:len(numericVersion.String())-1] + `)\.`)},
}

func proseGrammar(text string) ([]proseMapping, string) {
	if len(text) > 8192 {
		return nil, "UNRECOGNIZED_CONTENT"
	}
	for _, c := range []byte(text) {
		if c > 127 {
			return nil, "UNRECOGNIZED_CONTENT"
		}
	}
	mappings := []proseMapping{}
	seen := map[string]bool{}
	for cursor := 0; cursor < len(text); {
		if strings.ContainsRune(" \t\r\n", rune(text[cursor])) {
			cursor++
			continue
		}
		var match []string
		policyID := ""
		for _, form := range proseForms {
			match = form.pattern.FindStringSubmatch(text[cursor:])
			if match != nil {
				policyID = form.policy
				break
			}
		}
		if match == nil {
			return nil, "UNRECOGNIZED_CONTENT"
		}
		end := cursor + len(match[0])
		if end < len(text) && !strings.ContainsRune(" \t\r\n", rune(text[end])) {
			return nil, "UNRECOGNIZED_CONTENT"
		}
		canonical := "The version reported for requests by the PyPI JSON API is " + match[1] + "."
		if policyID == verificationPolicy {
			canonical = "The latest stable Python 3 release for Windows listed on Python.org is " + match[1] + "."
		}
		if seen[canonical] {
			return nil, "REPEATED_CLAIM"
		}
		if len(mappings) == 8 {
			return nil, "CLAIM_LIMIT"
		}
		seen[canonical] = true
		mappings = append(mappings, proseMapping{fmt.Sprintf("c%03d", len(mappings)+1), match[0], cursor, end, policyID, match[1], canonical})
		cursor = end
	}
	if len(mappings) == 0 {
		return nil, "NO_CLAIMS"
	}
	return mappings, "BOUNDED_GRAMMAR"
}

func validateProse(req verificationRequest, v proseResult, mode string, started, now time.Time) (Decision, error) {
	bad := errors.New("epochguard: invalid bounded prose contract")
	if req.SchemaVersion != proseSchema || req.PolicyID != prosePolicy || v.SchemaVersion != proseSchema || v.PolicyID != prosePolicy || v.RequestID != req.RequestID || v.Candidate != req.Candidate || v.CandidateSHA256 != req.CandidateSHA256 || shaText(v.Candidate) != v.CandidateSHA256 {
		return Unavailable, bad
	}
	mappings, reason := proseGrammar(req.Candidate)
	if v.ReasonCode != reason || len(v.Mappings) != len(mappings) {
		return Unavailable, bad
	}
	if reason != "BOUNDED_GRAMMAR" {
		if v.Coverage != "UNCERTAIN" || v.Verification != nil {
			return Unavailable, bad
		}
		return Unavailable, nil
	}
	if !reflect.DeepEqual(v.Mappings, mappings) || v.Coverage != "COMPLETE" || v.Verification == nil || len(v.Verification.Claims) != len(mappings) {
		return Unavailable, bad
	}
	sentences := make([]string, len(mappings))
	for i, m := range mappings {
		sentences[i] = m.Canonical
		if v.Verification.Claims[i].Claim.Source.ClaimID != m.ClaimID {
			return Unavailable, bad
		}
	}
	canonical := strings.Join(sentences, "\n")
	comparison := verificationRequest{multiSchema, multiPolicy, req.RequestID, canonical, shaText(canonical)}
	return validateMulti(comparison, *v.Verification, mode, started, now)
}

func newProseDecisionSource(cfg HTTPVerificationConfig) (*multiDecisionSource, error) {
	u, err := url.Parse(cfg.URL)
	if err != nil || u.Path != "/v1/verify/prose" || cfg.Mode != proseSchema {
		return nil, errors.New("epochguard: invalid prose configuration")
	}
	u.Path = "/v1/verify/multiclaim"
	original := cfg.URL
	cfg.URL, cfg.Mode = u.String(), multiSchema
	source, err := newMultiDecisionSource(cfg)
	if err != nil {
		return nil, err
	}
	source.endpoint, source.prose = original, true
	return source, nil
}
