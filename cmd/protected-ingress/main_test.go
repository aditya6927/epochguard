package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestFixtureKeySurvivesInitializationRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "receipt")
	if fixtureKey(path) != nil {
		t.Fatal("test initialization failed")
	}
	first, _ := os.ReadFile(path)
	if fixtureKey(path) != nil {
		t.Fatal("repeat initialization failed")
	}
	second, _ := os.ReadFile(path)
	if len(first) != 64 || !bytes.Equal(first, second) {
		t.Fatal("fixture key changed during dependency restart")
	}
	_ = os.WriteFile(path, []byte("invalid"), 0600)
	if fixtureKey(path) == nil {
		t.Fatal("invalid existing key silently replaced")
	}
}
