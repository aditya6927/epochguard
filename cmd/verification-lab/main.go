package main

import (
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/aditya6927/epochguard/internal/lab"
)

func main() {
	health := flag.Bool("healthcheck", false, "source-free local HTTP check")
	listen := flag.String("listen", "127.0.0.1:8787", "local HTTP listener")
	assets := flag.String("assets", "/app/web", "built frontend directory")
	flag.Parse()
	if *health {
		client := &http.Client{Timeout: 2 * time.Second}
		response, err := client.Get(lab.Origin + "/healthz")
		if err != nil {
			os.Exit(1)
		}
		response.Body.Close()
		if response.StatusCode != 200 {
			os.Exit(1)
		}
		return
	}
	h, err := lab.New(lab.Config{Ingress: "http://ingress:8082", Unsafe: "http://ingress-unsafe:8082", Assets: os.DirFS(*assets)})
	if err != nil {
		log.Fatal("Lab configuration unavailable")
	}
	defer h.Close()
	server := &http.Server{Addr: *listen, Handler: h, ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 3 * time.Second,
		WriteTimeout: 15 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192, ErrorLog: log.New(io.Discard, "", 0)}
	log.Print("EpochGuard Lab listening; fixture evidence only")
	if server.ListenAndServe() != nil {
		log.Fatal("Lab stopped")
	}
}
