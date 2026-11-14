package main

import (
	"crypto/rand"
	"encoding/hex"
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/aditya6927/epochguard/internal/ingress"
)

func main() {
	generate := flag.String("generate-fixture-secret", "", "test-only generated secret file")
	flag.Parse()
	if *generate != "" {
		if os.Getenv("EPOCHGUARD_TEST_MODE") != "1" {
			log.Fatal("fixture initialization unavailable")
		}
		if fixtureKey(*generate) != nil {
			log.Fatal("fixture initialization unavailable")
		}
		return
	}
	data, err := os.ReadFile(os.Getenv("EPOCHGUARD_ATTESTATION_SECRET_FILE"))
	if err != nil || len(data) > 66 {
		log.Fatal("ingress credentials unavailable")
	}
	key, err := hex.DecodeString(strings.TrimSuffix(strings.TrimSuffix(string(data), "\n"), "\r"))
	if err != nil || len(key) != 32 {
		log.Fatal("ingress credentials unavailable")
	}
	probe, err := os.ReadFile(os.Getenv("EPOCHGUARD_PROBE_FILE"))
	if err != nil || len(probe) > 8192 {
		log.Fatal("ingress probe unavailable")
	}
	h, err := ingress.New(ingress.Config{Gateway: os.Getenv("EPOCHGUARD_GATEWAY_URL"), Secret: key, ManagementToken: os.Getenv("EPOCHGUARD_SETUP_TOKEN"), ProbeCandidate: strings.TrimSuffix(string(probe), "\n")})
	if err != nil {
		log.Fatal("ingress configuration unavailable")
	}
	defer h.Close()
	server := &http.Server{Addr: ":8082", Handler: h, ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 3 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16 * 1024, ErrorLog: log.New(io.Discard, "", 0)}
	log.Print("protected ingress listening")
	if server.ListenAndServe() != nil {
		log.Fatal("ingress stopped")
	}
}

// Test initialization is idempotent across Compose dependency restarts. Never
// replace a key underneath a running ingress/gateway pair.
func fixtureKey(path string) error {
	if existing, err := os.ReadFile(path); err == nil {
		key, err := hex.DecodeString(string(existing))
		if err != nil || len(key) != 32 {
			return os.ErrInvalid
		}
		return nil
	} else if !os.IsNotExist(err) {
		return err
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	_, err = f.Write([]byte(hex.EncodeToString(key)))
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Chown(path, 10001, 10001)
}
