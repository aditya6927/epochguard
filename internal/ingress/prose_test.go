package ingress

import (
	"strings"
	"testing"
	"time"
)

func TestProsePolicyReceiptIsolation(t *testing.T) {
	nonce := strings.Repeat("a", 64)
	now := time.Now()
	for _, source := range []string{Policy, ProsePolicy} {
		for _, target := range []string{Policy, ProsePolicy} {
			for _, mutation := range []string{"valid", "nonce", "old", "body", "mac"} {
				r := fixtureReceipt(nonce)
				r.PolicyID = source
				body := []byte(testBody)
				if source == ProsePolicy {
					r.Version = BoundProtocol
					body = boundBody()
					r.BodySHA256 = Hash(body)
				}
				if mutation == "nonce" {
					r.Nonce = strings.Repeat("b", 64)
				}
				if mutation == "old" {
					r.IssuedAt -= 21
				}
				if mutation == "body" {
					body = append(body, ' ')
				}
				signed := sign(r, testKey)
				if source == ProsePolicy {
					signed = signedBound(BoundReceipt{r, Hash([]byte(testRequest))})
				}
				if mutation == "mac" {
					signed = "invalid"
				}
				var err error
				if target == ProsePolicy {
					_, err = verifyBound(signed, testKey, nonce, Hash([]byte(testRequest)), 200, body, now, now, target)
				} else {
					_, err = verifyPolicy(signed, testKey, nonce, 200, body, now, now, target)
				}
				if (err == nil) != (source == target && mutation == "valid") {
					t.Fatal("policy isolation/receipt attack")
				}
			}
		}
	}
}

func TestProseIngressProfiles(t *testing.T) {
	for _, profile := range []string{"004g", "004g-live"} {
		h, err := New(Config{Gateway: "http://gateway:8080", Secret: testKey, ManagementToken: "local-test", ProbeCandidate: LiveCanary, Profile: profile})
		if err != nil {
			t.Fatal(err)
		}
		if h.policy() != ProsePolicy {
			t.Fatal("wrong policy")
		}
		if profile == "004g-live" && h.cfg.Timeout != 44*time.Second {
			t.Fatal("wrong live deadline")
		}
		h.Close()
		if _, err := New(Config{Gateway: "http://gateway:8080", Secret: testKey, ManagementToken: "local-test", ProbeCandidate: testCandidate, Profile: profile}); err == nil {
			t.Fatal("source-consuming readiness accepted")
		}
	}
}
