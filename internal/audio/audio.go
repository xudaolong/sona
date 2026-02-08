package audio

import (
	"encoding/binary"
	"fmt"
	"io"
	"math"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/thewh1teagle/sona/internal/wav"
)

var verbose bool

type ReadOptions struct {
	EnhanceAudio bool
}

func SetVerbose(v bool) {
	verbose = v
}

// findFFmpeg checks for ffmpeg in this order:
// 1. System ffmpeg from $PATH
// 2. SONA_FFMPEG_PATH env var (warns and continues if set but not found)
// 3. Bundled ffmpeg next to the current binary
func findFFmpeg() (string, error) {
	path, err := exec.LookPath("ffmpeg")
	if err == nil {
		return path, nil
	}

	if envPath := os.Getenv("SONA_FFMPEG_PATH"); envPath != "" {
		if _, statErr := os.Stat(envPath); statErr == nil {
			return envPath, nil
		}
		fmt.Fprintf(os.Stderr, "warning: SONA_FFMPEG_PATH set to %q but not found, continuing search\n", envPath)
	}

	if exe, exErr := os.Executable(); exErr == nil {
		candidates := []string{
			filepath.Join(filepath.Dir(exe), "ffmpeg"),
			filepath.Join(filepath.Dir(exe), "ffmpeg.exe"),
		}
		for _, candidate := range candidates {
			if _, statErr := os.Stat(candidate); statErr == nil {
				return candidate, nil
			}
		}
	}

	return "", fmt.Errorf("ffmpeg not found: %w", err)
}

// convertWithFFmpeg writes the input to a temp file, runs ffmpeg to convert
// it to 16kHz mono s16le PCM via pipe output, and returns float32 samples.
func convertWithFFmpeg(r io.Reader, ffmpegPath string, opts ReadOptions) ([]float32, error) {
	tmp, err := os.CreateTemp("", "sona-*.audio")
	if err != nil {
		return nil, fmt.Errorf("failed to create temp file: %w", err)
	}
	defer os.Remove(tmp.Name())
	defer tmp.Close()

	if _, err := io.Copy(tmp, r); err != nil {
		return nil, fmt.Errorf("failed to write temp file: %w", err)
	}
	tmp.Close()

	args := []string{
		"-i", tmp.Name(),
		"-ar", "16000",
		"-ac", "1",
	}
	if opts.EnhanceAudio {
		// Quality-over-speed cleanup path to reduce transcription drift on noisy/long files.
		args = append(args, "-af", "silenceremove=stop_periods=-1:stop_duration=0.7:stop_threshold=-45dB")
	}
	args = append(args,
		"-f", "s16le",
		"-acodec", "pcm_s16le",
		"pipe:1",
	)

	cmd := exec.Command(ffmpegPath, args...)
	if verbose {
		cmd.Stderr = os.Stderr
	} else {
		cmd.Stderr = io.Discard
	}

	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("ffmpeg conversion failed: %w", err)
	}

	nSamples := len(out) / 2
	samples := make([]float32, nSamples)
	for i := 0; i < nSamples; i++ {
		sample := int16(binary.LittleEndian.Uint16(out[i*2 : i*2+2]))
		samples[i] = float32(float64(sample) / math.MaxInt16)
	}
	return samples, nil
}

// Read decodes audio from an io.ReadSeeker into float32 samples at 16kHz mono.
// If the input is a native 16kHz/mono/16-bit PCM WAV, it is decoded directly.
// Otherwise, ffmpeg is used to convert the audio.
func Read(r io.ReadSeeker) ([]float32, error) {
	return ReadWithOptions(r, ReadOptions{})
}

func ReadWithOptions(r io.ReadSeeker, opts ReadOptions) ([]float32, error) {
	h, err := wav.ReadHeader(r)
	if err == nil && h.IsNative() && !opts.EnhanceAudio {
		return wav.Read(r)
	}

	// Not a native WAV (or enhancement requested) — need ffmpeg
	r.Seek(0, io.SeekStart)
	ffmpegPath, err := findFFmpeg()
	if err != nil {
		if h.SampleRate != 0 {
			// It's a WAV but not native format
			return nil, fmt.Errorf("audio requires conversion (got %dHz %dch %dbit) but %w",
				h.SampleRate, h.Channels, h.BitsPerSample, err)
		}
		return nil, fmt.Errorf("unsupported audio format and %w", err)
	}

	return convertWithFFmpeg(r, ffmpegPath, opts)
}

// ReadFile opens an audio file by path and returns float32 samples at 16kHz mono.
func ReadFile(path string) ([]float32, error) {
	return ReadFileWithOptions(path, ReadOptions{})
}

func ReadFileWithOptions(path string, opts ReadOptions) ([]float32, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return ReadWithOptions(f, opts)
}
