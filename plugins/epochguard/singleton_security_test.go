package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
)

func TestSingletonCapturedBefore(t *testing.T) {
	data, err := os.ReadFile("../../tests/conformance/005ds-before.json")
	if err != nil {
		t.Fatal(err)
	}
	var captured struct {
		Multi multiResult
		Prose proseResult
	}
	if json.Unmarshal(data, &captured) != nil {
		t.Fatal("fixture")
	}
	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	v := captured.Multi
	req := verificationRequest{multiSchema, multiPolicy, v.RequestID, v.Candidate, shaText(v.Candidate)}
	got, err := validateMulti(req, v, "fixture", now.Add(-time.Second), now)
	if got != Unavailable || err == nil {
		t.Fatalf("forged multi authorized: %s %v", got, err)
	}
	t.Log("captured pre-fix COMPLETE/SUPPORTED record independently refused by Go multi validation")
	p := captured.Prose
	req = verificationRequest{proseSchema, prosePolicy, p.RequestID, p.Candidate, shaText(p.Candidate)}
	got, err = validateProse(req, p, "fixture", now.Add(-time.Second), now)
	if got != Unavailable || err == nil {
		t.Fatalf("forged prose authorized: %s %v", got, err)
	}
	t.Log("captured pre-fix COMPLETE/SUPPORTED record independently refused by Go prose validation")
}

func TestSingletonIndependentGrammars(t *testing.T) {
	for _, policy := range []string{verificationPolicy, pypiPolicy} {
		for _, versions := range [][2]string{{"3.88.7", "3.88.6"}, {"3.88.6", "3.88.7"}, {"3.88.7", "3.88.7"}} {
			form := "The latest stable Python 3 release for Windows listed on Python.org is %s."
			if policy == pypiPolicy {
				form = "The version reported for requests by the PyPI JSON API is %s."
			}
			text := fmt.Sprintf(form, versions[0]) + "\n" + fmt.Sprintf(form, versions[1])
			if mappings, reason := multiGrammar(text); len(mappings) != 0 || reason != "REPEATED_CLAIM" {
				t.Fatal("multi partial conflict")
			}
			if mappings, reason := proseGrammar(text); len(mappings) != 0 || reason != "REPEATED_CLAIM" {
				t.Fatal("prose partial conflict")
			}
		}
	}
	// The wire bound stays eight even though two singleton policies permit only
	// two admitted assertions. A repeat is detected before reaching that bound.
	text := strings.Repeat("The version reported for requests by the PyPI JSON API is 2.88.7.\n", 9)
	if mappings, reason := multiGrammar(text); len(mappings) != 0 || reason != "REPEATED_CLAIM" {
		t.Fatal("multi repeated wire-bound input")
	}
}
