package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/url"
	"reflect"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/maximhq/bifrost/core/schemas"
)

const multiSchema = "004b.v1"
const multiPolicy = "multi-claim-templates-v1"
const pypiPolicy = "pypi-requests-reported-v1"
const pypiURL = "https://pypi.org/pypi/requests/json"
const multiBodyLimit = 256 * 1024

var numericVersion = regexp.MustCompile(`^(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})$`)
var pythonSentence = regexp.MustCompile(`^The latest stable Python 3 release for Windows listed on Python\.org is (` + versionPattern + `)\.`)
var pypiSentence = regexp.MustCompile(`^The version reported for requests by the PyPI JSON API is ((?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2}))\.`)

type multiSource struct {
	ClaimID               string   `json:"claim_id"`
	SourceText            string   `json:"source_text"`
	Start                 int      `json:"start"`
	End                   int      `json:"end"`
	NormalizedProposition *string  `json:"normalized_proposition"`
	Factuality            string   `json:"factuality"`
	Temporal              string   `json:"temporal"`
	FreshEvidence         string   `json:"fresh_evidence"`
	Uncertainty           []string `json:"uncertainty"`
	TemporalReference     *string  `json:"temporal_reference"`
}
type multiBound struct {
	Source          multiSource `json:"source"`
	CandidateSHA256 string      `json:"candidate_sha256"`
	PolicyID        string      `json:"policy_id"`
	Version         string      `json:"version"`
}
type multiEvidence struct {
	EvidenceID      string    `json:"evidence_id"`
	URL             string    `json:"url"`
	RetrievalMode   string    `json:"retrieval_mode"`
	RetrievalID     string    `json:"retrieval_id"`
	ContentSHA256   string    `json:"content_sha256"`
	ObservedVersion string    `json:"observed_version"`
	RetrievedAt     time.Time `json:"retrieved_at"`
	ObservedAt      time.Time `json:"observed_at"`
}
type multiClaimResult struct {
	Claim                         multiBound      `json:"claim"`
	Verdict                       string          `json:"verdict"`
	ReasonCode                    string          `json:"reason_code"`
	EvidenceRequirementsSatisfied bool            `json:"evidence_requirements_satisfied"`
	Evidence                      []multiEvidence `json:"evidence"`
}
type multiExtraction struct {
	SchemaVersion string        `json:"schema_version"`
	Claims        []multiSource `json:"claims"`
}
type multiCoverage struct {
	Status           string   `json:"status"`
	ReasonCode       string   `json:"reason_code"`
	RequiredClaimIDs []string `json:"required_claim_ids"`
}
type multiResult struct {
	SchemaVersion    string             `json:"schema_version"`
	PolicyID         string             `json:"policy_id"`
	RequestID        string             `json:"request_id"`
	Candidate        string             `json:"candidate"`
	CandidateSHA256  string             `json:"candidate_sha256"`
	ExtractionStatus string             `json:"extraction_status"`
	BindingStatus    string             `json:"binding_status"`
	Extraction       *multiExtraction   `json:"extraction"`
	Coverage         multiCoverage      `json:"coverage"`
	Claims           []multiClaimResult `json:"claims"`
	Verdict          string             `json:"verdict"`
	CheckedAt        time.Time          `json:"checked_at"`
}

func shaText(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}
func multiTextBound(text string) bool {
	if !utf8.ValidString(text) || len(text) > 32768 || utf8.RuneCountInString(text) > 8192 {
		return false
	}
	for _, c := range text {
		if c < 32 && c != '\t' && c != '\r' && c != '\n' {
			return false
		}
	}
	return true
}

// Independent scanner: accepted grammar is ASCII. We still explicitly convert
// byte positions into Python code-point offsets and reject all unknown content.
func multiGrammar(text string) ([]multiBound, string) {
	var required []multiBound
	seen := map[string]bool{}
	for cursor := 0; cursor < len(text); {
		if strings.ContainsRune(" \t\r\n", rune(text[cursor])) {
			cursor++
			continue
		}
		match, policyID := pythonSentence.FindStringSubmatch(text[cursor:]), verificationPolicy
		if match == nil {
			match, policyID = pypiSentence.FindStringSubmatch(text[cursor:]), pypiPolicy
		}
		if match == nil {
			return nil, "UNRECOGNIZED_CONTENT"
		}
		end := cursor + len(match[0])
		if end < len(text) && !strings.ContainsRune(" \t\r\n", rune(text[end])) {
			return nil, "UNRECOGNIZED_CONTENT"
		}
		if seen[match[0]] {
			return nil, "REPEATED_CLAIM"
		}
		if len(required) == 8 {
			return nil, "CLAIM_LIMIT"
		}
		seen[match[0]] = true
		source := multiSource{ClaimID: fmt.Sprintf("c%03d", len(required)+1), SourceText: match[0],
			Start: utf8.RuneCountInString(text[:cursor]), End: utf8.RuneCountInString(text[:end]),
			Factuality: "FACTUAL", Temporal: "DYNAMIC", FreshEvidence: "REQUIRED", Uncertainty: []string{}}
		required = append(required, multiBound{source, shaText(text), policyID, match[1]})
		cursor = end
	}
	if len(required) == 0 {
		return nil, "NO_CLAIMS"
	}
	return required, "EXACT_TEMPLATES"
}

// Unlike encoding/json's struct matcher, this checks exact field names AND all
// required fields, types, nullable positions, array counts and depth before decode.
// The existing 003A parser is deliberately left unchanged.
func strictMultiJSON(data []byte, target *multiResult) error {
	bad := errors.New("epochguard: invalid multiclaim contract")
	if len(data) > multiBodyLimit || !utf8.Valid(data) {
		return bad
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var walk func(reflect.Type, int) error
	walk = func(t reflect.Type, depth int) error {
		if depth > 8 {
			return bad
		}
		token, err := dec.Token()
		if err != nil {
			return bad
		}
		if t.Kind() == reflect.Pointer {
			if token == nil {
				return nil
			}
			t = t.Elem()
		}
		if t == reflect.TypeOf(time.Time{}) {
			if _, ok := token.(string); !ok {
				return bad
			}
			return nil
		}
		switch t.Kind() {
		case reflect.Struct:
			if token != json.Delim('{') {
				return bad
			}
			fields := map[string]reflect.Type{}
			for i := 0; i < t.NumField(); i++ {
				f := t.Field(i)
				fields[f.Tag.Get("json")] = f.Type
			}
			for dec.More() {
				key, err := dec.Token()
				name, ok := key.(string)
				child, exists := fields[name]
				if err != nil || !ok || !exists {
					return bad
				}
				delete(fields, name)
				if err := walk(child, depth+1); err != nil {
					return bad
				}
			}
			end, err := dec.Token()
			if err != nil || end != json.Delim('}') || len(fields) != 0 {
				return bad
			}
		case reflect.Slice:
			if token != json.Delim('[') {
				return bad
			}
			for count := 0; dec.More(); count++ {
				if count >= 8 || walk(t.Elem(), depth+1) != nil {
					return bad
				}
			}
			end, err := dec.Token()
			if err != nil || end != json.Delim(']') {
				return bad
			}
		case reflect.String:
			value, ok := token.(string)
			if !ok || utf8.RuneCountInString(value) > 8192 {
				return bad
			}
		case reflect.Int:
			if _, ok := token.(json.Number); !ok {
				return bad
			}
		case reflect.Bool:
			if _, ok := token.(bool); !ok {
				return bad
			}
		default:
			return bad
		}
		return nil
	}
	if walk(reflect.TypeOf(*target), 0) != nil {
		return bad
	}
	if _, err := dec.Token(); err != io.EOF {
		return bad
	}
	return json.Unmarshal(data, target)
}

func validMultiSource(actual, expected multiSource) bool {
	identity := actual
	identity.NormalizedProposition, identity.TemporalReference = nil, nil
	identity.Uncertainty = []string{}
	if !reflect.DeepEqual(identity, expected) || len(actual.Uncertainty) > 6 {
		return false
	}
	seen := map[string]bool{}
	for _, value := range actual.Uncertainty {
		switch value {
		case "MISSING_CONTEXT", "AMBIGUOUS_REFERENCE", "MIXED_REQUIREMENTS", "MODEL_ABSTENTION", "BASELINE_HEURISTIC", "UNTRUSTED_INSTRUCTION":
		default:
			return false
		}
		if seen[value] {
			return false
		}
		seen[value] = true
	}
	return actual.TemporalReference == nil || (*actual.TemporalReference != "" && utf8.RuneCountInString(*actual.TemporalReference) <= 160 && strings.Contains(actual.SourceText, *actual.TemporalReference))
}

func validateMulti(req verificationRequest, v multiResult, mode string, started, now time.Time) (Decision, error) {
	bad := errors.New("epochguard: invalid multiclaim contract")
	if mode != "fixture" && mode != "live" {
		return Unavailable, bad
	}
	if v.SchemaVersion != multiSchema || v.PolicyID != multiPolicy || v.RequestID != req.RequestID || v.Candidate != req.Candidate || v.CandidateSHA256 != req.CandidateSHA256 || shaText(v.Candidate) != v.CandidateSHA256 || !multiTextBound(v.Candidate) || v.CheckedAt.Before(started.Add(-2*time.Second)) || v.CheckedAt.After(now.Add(2*time.Second)) {
		return Unavailable, bad
	}
	required, reason := multiGrammar(req.Candidate)
	if reason != "EXACT_TEMPLATES" {
		// No authorization is possible on an unrecognized candidate. Accept only
		// the exact early coverage refusal produced by the grammar boundary.
		if v.Coverage.Status != "UNCERTAIN" || v.Coverage.ReasonCode != reason || len(v.Coverage.RequiredClaimIDs) != 0 || v.ExtractionStatus != "NOT_RUN" || v.BindingStatus != "NOT_RUN" || v.Extraction != nil || len(v.Claims) != 0 || v.Verdict != "INSUFFICIENT" {
			return Unavailable, bad
		}
		return Unavailable, nil
	}
	if v.Coverage.Status != "COMPLETE" || v.Coverage.ReasonCode != "EXACT_TEMPLATES" || len(v.Coverage.RequiredClaimIDs) != len(required) || (v.ExtractionStatus != "TRUSTED_GRAMMAR" && v.ExtractionStatus != "VALIDATED") || v.BindingStatus != "VALID" || v.Extraction == nil || v.Extraction.SchemaVersion != "004a.v1" || len(v.Extraction.Claims) != len(required) {
		return Unavailable, bad
	}
	for i, claim := range required {
		if v.Coverage.RequiredClaimIDs[i] != claim.Source.ClaimID || !validMultiSource(v.Extraction.Claims[i], claim.Source) {
			return Unavailable, bad
		}
	}
	last, supported, contradicted := -1, 0, false
	for _, result := range v.Claims {
		index := -1
		for i := range required {
			if required[i].Source.ClaimID == result.Claim.Source.ClaimID {
				index = i
			}
		}
		if index <= last || index < 0 || !reflect.DeepEqual(result.Claim, required[index]) || len(result.Evidence) > 1 || result.EvidenceRequirementsSatisfied != (len(result.Evidence) == 1) {
			return Unavailable, bad
		}
		last = index
		if len(result.Evidence) == 0 {
			if result.Verdict != "INSUFFICIENT" {
				return Unavailable, bad
			}
			switch result.ReasonCode {
			case "UNSUPPORTED_CLAIM", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_EVIDENCE", "RETRIEVAL_TIMEOUT", "RETRIEVAL_FAILURE", "VERIFIER_ERROR", "STALE_OBSERVATION":
			default:
				return Unavailable, bad
			}
			continue
		}
		e := result.Evidence[0]
		url, liveMode, matchReason, olderReason := primaryURL, "tavily_live", "MATCHED_PRIMARY_LABEL", "OLDER_THAN_PRIMARY_LABEL"
		if result.Claim.PolicyID == pypiPolicy {
			url, liveMode, matchReason, olderReason = pypiURL, "pypi_live", "MATCHED_PYPI_VERSION", "OLDER_THAN_PYPI_VERSION"
		}
		expectedMode := liveMode
		if mode == "fixture" {
			expectedMode = "fixture"
		}
		if e.URL != url || e.RetrievalMode != expectedMode || !digestRE.MatchString(e.ContentSHA256) || !retrievalIDRE.MatchString(e.RetrievalID) || !numericVersion.MatchString(e.ObservedVersion) || (url == primaryURL && !versionRE.MatchString(e.ObservedVersion)) || e.EvidenceID != shaText(e.URL+"|"+e.RetrievalMode+"|"+e.RetrievalID+"|"+e.ContentSHA256) || !e.RetrievedAt.Equal(e.ObservedAt) || e.ObservedAt.Before(started.Add(-2*time.Second)) || e.ObservedAt.After(v.CheckedAt) || e.ObservedAt.After(now.Add(2*time.Second)) || now.Sub(e.ObservedAt) > time.Minute {
			return Unavailable, bad
		}
		expectedVerdict, expectedReason := "INSUFFICIENT", "CLAIM_AHEAD_OF_SOURCE"
		switch compareVersion(result.Claim.Version, e.ObservedVersion) {
		case 0:
			expectedVerdict, expectedReason = "SUPPORTED", matchReason
			supported++
		case -1:
			expectedVerdict, expectedReason, contradicted = "CONTRADICTED", olderReason, true
		}
		if result.Verdict != expectedVerdict || result.ReasonCode != expectedReason {
			return Unavailable, bad
		}
	}
	derived, decision := "INSUFFICIENT", Unavailable
	if contradicted {
		derived, decision = "CONTRADICTED", Reject
	} else if supported == len(required) {
		derived, decision = "SUPPORTED", Allow
	}
	if v.Verdict != derived {
		return Unavailable, bad
	}
	return decision, nil
}

type multiDecisionSource struct{ *httpDecisionSource }

func newMultiDecisionSource(cfg HTTPVerificationConfig) (*multiDecisionSource, error) {
	u, err := url.Parse(cfg.URL)
	if err != nil || u.Path != "/v1/verify/multiclaim" || cfg.Mode != multiSchema || (cfg.EvidenceMode != "fixture" && cfg.EvidenceMode != "live") {
		return nil, errors.New("epochguard: invalid multiclaim configuration")
	}
	// Reuse the bounded, immutable HTTP transport constructor after separately
	// validating the discriminator/endpoint; this is not a request-time fallback.
	u.Path = "/v1/verify"
	transportCfg := cfg
	transportCfg.URL, transportCfg.Mode, transportCfg.EvidenceMode = u.String(), verificationSchema, "tavily_live"
	source, err := newHTTPDecisionSource(transportCfg)
	if err != nil {
		return nil, err
	}
	source.endpoint, source.evidenceMode = cfg.URL, cfg.EvidenceMode
	return &multiDecisionSource{source}, nil
}

func (s *multiDecisionSource) Decide(ctx context.Context, resp *schemas.BifrostResponse) (Decision, error) {
	started := time.Now()
	text, err := bufferedCandidate(resp)
	if err != nil || !multiTextBound(text) {
		return Unavailable, verificationFailure{category: "unsupported_candidate"}
	}
	// The pinned BifrostResponse is a pointer union. A mixed response cannot
	// establish that this chat candidate accounts for the whole output.
	value := reflect.ValueOf(resp).Elem()
	for i := 0; i < value.NumField(); i++ {
		if value.Type().Field(i).Name != "ChatResponse" && (value.Field(i).Kind() != reflect.Pointer || !value.Field(i).IsNil()) {
			return Unavailable, verificationFailure{category: "unsupported_candidate"}
		}
	}
	// Additional provider annotations on 004B require a separate trust policy.
	chat := resp.ChatResponse
	if len(chat.PromptFilterResults) != 0 || len(chat.Choices[0].ContentFilterResults) != 0 || chat.Diagnostics != nil || len(chat.ExtraParams) != 0 || chat.Choices[0].StopString != nil {
		return Unavailable, verificationFailure{category: "unsupported_candidate"}
	}
	nonce := make([]byte, 16)
	if _, err := rand.Read(nonce); err != nil {
		return Unavailable, verificationFailure{category: "verification_unavailable"}
	}
	payload := verificationRequest{multiSchema, multiPolicy, hex.EncodeToString(nonce), text, shaText(text)}
	body, err := json.Marshal(payload)
	if err != nil || len(body) > 65536 {
		return Unavailable, verificationFailure{category: "request_failure"}
	}
	req, err := http.NewRequestWithContext(ctx, "POST", s.endpoint, bytes.NewReader(body))
	if err != nil {
		return Unavailable, verificationFailure{category: "request_failure"}
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := s.client.Do(req)
	if err != nil {
		return Unavailable, transportFailure(err)
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return Unavailable, verificationFailure{category: "verifier_http_failure", status: response.StatusCode}
	}
	media, _, _ := mime.ParseMediaType(response.Header.Get("Content-Type"))
	data, err := io.ReadAll(io.LimitReader(response.Body, multiBodyLimit+1))
	if err != nil {
		return Unavailable, transportFailure(err)
	}
	var result multiResult
	if media != "application/json" || strictMultiJSON(data, &result) != nil {
		return Unavailable, verificationFailure{category: "invalid_contract", status: 200}
	}
	decision, err := validateMulti(payload, result, s.evidenceMode, started, time.Now())
	if err != nil {
		return Unavailable, verificationFailure{category: "invalid_contract", status: 200}
	}
	safeLogf("epochguard verification_schema=004b.v1 verification_verdict=%s", result.Verdict)
	return decision, nil
}
