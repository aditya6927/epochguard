package ingress

import (
	"strings"
	"testing"
)

func TestModelQualificationAdmission(t *testing.T) {
	base := `{"model":"gemini/gemini-selected-by-operator","messages":[{"role":"user","content":"candidate cannot select policies"}],"stream":false,"max_completion_tokens":256}`
	if !validQualifiedRequest([]byte(base), true) || validRequest([]byte(base)) {
		t.Fatal("qualification admission crossed ordinary profile")
	}
	for _, change := range []struct{ old, new string }{
		{"256", "1025"}, {"256", "127"}, {"256", "null"}, {"256", "true"}, {"256", "256.0"},
		{"max_completion_tokens", "Max_Completion_Tokens"}, {"false", "true"},
		{`"stream":false`, `"fallbacks":["fixture/epochguard-test"],"stream":false`},
		{`"stream":false`, `"policy":"ALLOW","stream":false`},
		{"gemini/gemini-selected-by-operator", "fixture/epochguard-test"},
	} {
		if validQualifiedRequest([]byte(strings.Replace(base, change.old, change.new, 1)), true) {
			t.Fatal("unsafe model request admitted")
		}
	}
	if validQualifiedRequest([]byte(strings.Replace(base, `,"max_completion_tokens":256`, "", 1)), true) {
		t.Fatal("missing output bound admitted")
	}
}

func TestModelQualificationRequiresBoundProseProfile(t *testing.T) {
	for _, profile := range []string{"", "004e-live", "004g"} {
		if h, err := New(Config{Profile: profile, ModelQualification: true}); err == nil {
			h.Close()
			t.Fatal("qualification enabled outside explicit bounded profile")
		}
	}
}
