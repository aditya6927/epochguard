package main

import (
	"bufio"
	"bytes"
	"testing"
)

func TestCommandPreservesBinaryAndPipeline(t *testing.T) {
	first := []byte("*3\r\n$4\r\nHSET\r\n$1\r\nk\r\n$5\r\na\x00\r\nb\r\n")
	second := []byte("*1\r\n$4\r\nPING\r\n")
	r := bufio.NewReader(bytes.NewReader(append(append([]byte{}, first...), second...)))
	raw, args, err := readCommand(r)
	if err != nil || !bytes.Equal(raw, first) || args[2] != "a\x00\r\nb" {
		t.Fatalf("binary command changed: %v", err)
	}
	raw, args, err = readCommand(r)
	if err != nil || !bytes.Equal(raw, second) || args[0] != "PING" {
		t.Fatal("pipeline boundary lost")
	}
}

func TestCommandRejectsInvalidFrames(t *testing.T) {
	for _, s := range []string{"PING\r\n", "*0\r\n", "*2\r\n$4\r\nPING\r\n", "*1\r\n$999999999\r\n", "*1\r\n$1\r\naXX"} {
		if _, _, err := readCommand(bufio.NewReader(bytes.NewBufferString(s))); err == nil {
			t.Fatal("invalid command accepted")
		}
	}
}
