# /// script
# requires-python = ">=3.12"
# dependencies = ["sonapy"]
#
# [tool.uv.sources]
# sonapy = { path = "../" }
# ///
"""
Basic sonapy usage — spawn sona, load a model, transcribe.

Setup:
  wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
  wget https://github.com/ggml-org/whisper.cpp/raw/refs/heads/master/samples/jfk.wav

Run:
  uv run examples/basic.py ggml-tiny.bin jfk.wav
"""

import sys
from sonapy import Sona


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <model.bin> <audio.wav>")
        sys.exit(1)

    model_path = sys.argv[1]
    audio_path = sys.argv[2]

    with Sona() as sona:
        print(f"Sona running on port {sona.port}")

        # Load model
        print(f"Loading model: {model_path}")
        sona.load_model(model_path)

        # Check ready
        status = sona.ready()
        print(f"Ready: {status}")

        # Transcribe — default json format
        print("Transcribing...")
        result = sona.transcribe(audio_path)
        print(f"Text: {result['text']}")

        # Transcribe — verbose_json with timestamps
        result = sona.transcribe(audio_path, response_format="verbose_json")
        for seg in result["segments"]:
            print(f"  [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}")

        # Transcribe — SRT subtitles
        srt = sona.transcribe(audio_path, response_format="srt")
        print(f"\nSRT output:\n{srt}")


if __name__ == "__main__":
    main()
