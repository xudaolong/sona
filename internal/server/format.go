package server

import (
	"fmt"
	"strings"

	"github.com/thewh1teagle/sona/internal/whisper"
)

// csToSeconds converts whisper centiseconds (10ms units) to seconds.
func csToSeconds(cs int64) float64 {
	return float64(cs) / 100.0
}

// csToSRTTime converts centiseconds to SRT timestamp format HH:MM:SS,mmm.
func csToSRTTime(cs int64) string {
	ms := cs * 10
	s := ms / 1000
	ms = ms % 1000
	m := s / 60
	s = s % 60
	h := m / 60
	m = m % 60
	return fmt.Sprintf("%02d:%02d:%02d,%03d", h, m, s, ms)
}

// csToVTTTime converts centiseconds to WebVTT timestamp format HH:MM:SS.mmm.
func csToVTTTime(cs int64) string {
	ms := cs * 10
	s := ms / 1000
	ms = ms % 1000
	m := s / 60
	s = s % 60
	h := m / 60
	m = m % 60
	return fmt.Sprintf("%02d:%02d:%02d.%03d", h, m, s, ms)
}

// formatSRT formats segments as SubRip (.srt) subtitles.
func formatSRT(segments []whisper.Segment) string {
	var sb strings.Builder
	for i, seg := range segments {
		if i > 0 {
			sb.WriteByte('\n')
		}
		fmt.Fprintf(&sb, "%d\n%s --> %s\n%s\n",
			i+1,
			csToSRTTime(seg.Start),
			csToSRTTime(seg.End),
			strings.TrimSpace(seg.Text),
		)
	}
	return sb.String()
}

// formatVTT formats segments as WebVTT (.vtt) subtitles.
func formatVTT(segments []whisper.Segment) string {
	var sb strings.Builder
	sb.WriteString("WEBVTT\n\n")
	for i, seg := range segments {
		if i > 0 {
			sb.WriteByte('\n')
		}
		fmt.Fprintf(&sb, "%s --> %s\n%s\n",
			csToVTTTime(seg.Start),
			csToVTTTime(seg.End),
			strings.TrimSpace(seg.Text),
		)
	}
	return sb.String()
}

// verboseSegment is the JSON representation of a segment in verbose_json format.
type verboseSegment struct {
	Start float64 `json:"start"`
	End   float64 `json:"end"`
	Text  string  `json:"text"`
}

// verboseJSON is the response body for response_format=verbose_json.
type verboseJSON struct {
	Text     string           `json:"text"`
	Segments []verboseSegment `json:"segments"`
}

// buildVerboseJSON creates the verbose_json response structure.
func buildVerboseJSON(segments []whisper.Segment) verboseJSON {
	text := whisper.TranscribeResult{Segments: segments}.Text()
	vSegs := make([]verboseSegment, len(segments))
	for i, seg := range segments {
		vSegs[i] = verboseSegment{
			Start: csToSeconds(seg.Start),
			End:   csToSeconds(seg.End),
			Text:  seg.Text,
		}
	}
	return verboseJSON{Text: text, Segments: vSegs}
}
