//go:build routeaudit

// Test-only native observer. Never loaded by the normal deployments.
package main

import (
	"encoding/json"
	"net"
	"net/http"
	"sync"

	"github.com/maximhq/bifrost/core/schemas"
)

type event struct {
	Phase string `json:"phase"`
	Path  string `json:"path,omitempty"`
	Kind  string `json:"kind,omitempty"`
	Code  string `json:"code,omitempty"`
}

var mu sync.Mutex
var events []event
var server *http.Server

func GetName() string { return "routeobserver" }
func Init(any) error {
	listener, err := net.Listen("tcp", ":9010")
	if err != nil {
		return err
	}
	server = &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(events)
	})}
	go server.Serve(listener)
	return nil
}
func Cleanup() error { return server.Close() }
func appendEvent(e event) {
	mu.Lock()
	defer mu.Unlock()
	if len(events) < 4096 {
		events = append(events, e)
	}
}
func HTTPTransportPreHook(_ *schemas.BifrostContext, req *schemas.HTTPRequest) (*schemas.HTTPResponse, error) {
	appendEvent(event{Phase: "http_pre", Path: req.Path})
	return nil, nil
}
func PreRequestHook(_ *schemas.BifrostContext, req *schemas.BifrostRequest) error {
	appendEvent(event{Phase: "pre_request", Kind: string(req.RequestType)})
	return nil
}
func PreLLMHook(_ *schemas.BifrostContext, req *schemas.BifrostRequest) (*schemas.BifrostRequest, *schemas.LLMPluginShortCircuit, error) {
	appendEvent(event{Phase: "pre_llm", Kind: string(req.RequestType)})
	return req, nil, nil
}
func PostLLMHook(_ *schemas.BifrostContext, resp *schemas.BifrostResponse, err *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError, error) {
	e := event{Phase: "post_llm"}
	if err != nil && err.Error != nil && err.Error.Code != nil {
		e.Code = *err.Error.Code
	}
	appendEvent(e)
	return resp, err, nil
}
