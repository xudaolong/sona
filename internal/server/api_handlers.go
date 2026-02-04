package server

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/thewh1teagle/sona/internal/audio"
	"github.com/thewh1teagle/sona/internal/whisper"
)

func (s *Server) handleTranscription(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)

	file, _, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, "missing or invalid 'file' field: "+err.Error())
		return
	}
	defer file.Close()

	samples, err := audio.ReadWithOptions(file, audio.ReadOptions{
		EnhanceAudio: parseBoolFormValue(r.FormValue("enhance_audio")),
	})
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid audio file: "+err.Error())
		return
	}

	opts := whisper.TranscribeOptions{
		Language:       r.FormValue("language"),
		DetectLanguage: parseBoolFormValue(r.FormValue("detect_language")),
		Prompt:         r.FormValue("prompt"),
		Verbose:        s.verbose,
	}

	s.mu.Lock()
	text, err := s.ctx.Transcribe(samples, opts)
	s.mu.Unlock()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "transcription failed: "+err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"text": text})
}

func (s *Server) handleModels(w http.ResponseWriter, r *http.Request) {
	now := time.Now().Unix()
	resp := map[string]any{
		"object": "list",
		"data": []map[string]any{
			{
				"id":       s.modelName,
				"object":   "model",
				"created":  now,
				"owned_by": "local",
			},
		},
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}
