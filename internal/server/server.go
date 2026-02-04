package server

import (
	"fmt"
	"log"
	"net/http"
	"path/filepath"
	"sync"

	"github.com/thewh1teagle/sona/internal/whisper"
)

const maxUploadSize = 1 << 30 // 1 GB

type Server struct {
	ctx       *whisper.Context
	mu        sync.Mutex
	modelName string
	verbose   bool
}

func New(ctx *whisper.Context, modelPath string, verbose bool) *Server {
	return &Server{
		ctx:       ctx,
		modelName: filepath.Base(modelPath),
		verbose:   verbose,
	}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/audio/transcriptions", s.handleTranscription)
	mux.HandleFunc("GET /v1/models", s.handleModels)
	s.registerDocsRoutes(mux)
	return mux
}

func ListenAndServe(addr string, s *Server) error {
	log.Printf("listening on %s", addr)
	fmt.Printf("listening on %s\n", addr)
	return http.ListenAndServe(addr, s.Handler())
}
