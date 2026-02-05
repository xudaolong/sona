# /// script
# requires-python = ">=3.12"
# dependencies = ["sonapy"]
#
# [tool.uv.sources]
# sonapy = { path = "../" }
# ///
"""
Streaming transcription — see progress and segments in real time.

Setup:
  wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
  wget https://github.com/ggml-org/whisper.cpp/raw/refs/heads/master/samples/jfk.wav

Run:
  uv run examples/streaming.py ggml-tiny.bin jfk.wav
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
        sona.load_model(model_path)

        print("Streaming transcription:")
        for event in sona.transcribe(audio_path, stream=True):
            match event["type"]:
                case "progress":
                    print(f"  progress: {event['progress']}%")
                case "segment":
                    print(f"  [{event['start']:.1f}s] {event['text']}")
                case "result":
                    print(f"\nFinal: {event['text']}")


if __name__ == "__main__":
    main()
