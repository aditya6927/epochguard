//go:build deploymenttest

// Isolated loader failure control. Never loaded by the regular deployments.
package main

import "errors"

func Init(any) error  { return errors.New("deliberate isolated initialization failure") }
func GetName() string { return "epochguard" }
func Cleanup() error  { return nil }
