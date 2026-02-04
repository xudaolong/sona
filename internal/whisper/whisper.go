package whisper

import "errors"

var ErrNotImplemented = errors.New("whisper: not implemented on this platform")

// TranscribeOptions controls transcription behavior.
type TranscribeOptions struct {
	Language       string // e.g. "en", "he" (empty = whisper.cpp default: "en")
	DetectLanguage bool   // auto-detect language (whisper.cpp detect_language)
	Translate      bool   // translate to English
	Threads        int    // CPU threads (0 = whisper default)
	Prompt         string // initial prompt / vocabulary hint
	Verbose        bool   // enable whisper/ggml logs
}
