package ingress

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func signedBound(value any) string {
	payload, _ := json.Marshal(value)
	mac := hmac.New(sha256.New, testKey)
	_, _ = mac.Write(payload)
	return base64.RawURLEncoding.EncodeToString(payload) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func boundBody() []byte {
	body, _ := json.Marshal(map[string]any{"object": "chat.completion", "choices": []any{map[string]any{"index": 0, "finish_reason": "stop", "message": map[string]string{"role": "assistant", "content": testCandidate}}}})
	return body
}

func TestBoundReceiptAdversaries(t *testing.T) {
	now := time.Now()
	nonce := strings.Repeat("a", 64)
	requestHash := Hash([]byte(testRequest))
	for _, mode := range []string{"valid", "request", "missing", "empty", "old-version", "legacy-wire", "cross-policy", "old-time", "nonce", "body", "extra", "duplicate", "alias", "mac", "metadata"} {
		t.Run(mode, func(t *testing.T) {
			body := boundBody()
			r := BoundReceipt{Receipt{BoundProtocol, nonce, ProsePolicy, "ALLOW", 200, Hash(body), Hash([]byte(testCandidate)), now.Unix()}, requestHash}
			switch mode {
			case "request":
				r.RequestSHA256 = Hash([]byte(testRequest + " "))
			case "empty":
				r.RequestSHA256 = ""
			case "old-version":
				r.Version = Protocol
			case "cross-policy":
				r.PolicyID = Policy
			case "old-time":
				r.IssuedAt -= 21
			case "nonce":
				r.Nonce = strings.Repeat("b", 64)
			case "body":
				body = append(body, ' ')
			case "metadata":
				var root map[string]any
				_ = json.Unmarshal(body, &root)
				root["id"] = "UNVERIFIED"
				body, _ = json.Marshal(root)
				r.BodySHA256 = Hash(body)
			}
			header := signedBound(r)
			if mode == "legacy-wire" {
				header = signedBound(r.Receipt)
			}
			if mode == "missing" || mode == "extra" || mode == "alias" {
				raw, _ := json.Marshal(r)
				var fields map[string]any
				_ = json.Unmarshal(raw, &fields)
				if mode == "missing" {
					delete(fields, "request_sha256")
				}
				if mode == "extra" {
					fields["unexpected"] = true
				}
				if mode == "alias" {
					fields["Request_sha256"] = fields["request_sha256"]
					delete(fields, "request_sha256")
				}
				header = signedBound(fields)
			}
			if mode == "duplicate" {
				raw, _ := json.Marshal(r)
				raw = bytes.Replace(raw, []byte(`"request_sha256":`), []byte(`"request_sha256":"`+requestHash+`","request_sha256":`), 1)
				mac := hmac.New(sha256.New, testKey)
				_, _ = mac.Write(raw)
				header = base64.RawURLEncoding.EncodeToString(raw) + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
			}
			if mode == "mac" {
				header = "invalid"
			}
			_, err := verifyBound(header, testKey, nonce, requestHash, 200, body, now, now, ProsePolicy)
			if (err == nil) != (mode == "valid") {
				t.Fatal("bound receipt check failed")
			}
			if mode == "valid" {
				if _, err := Verify(header, testKey, nonce, 200, body, now, now); err == nil {
					t.Fatal("old profile accepted new wire")
				}
			}
		})
	}
}
