# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx==0.28.1",
# ]
# ///

"""Package a Sona release archive with a bundled ffmpeg binary."""

import argparse
import io
import shutil
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

import httpx


# 每个目标按顺序尝试：gyan.dev / osxexperts 会偶发 5xx（2026-10-25 的 v0.3.2
# Windows 打包就因 503 整条发布失败），BtbN 的 latest 标签是固定资产名的 GitHub
# 兜底。压缩包内部目录结构不同，但取的都是 basename=ffmpeg(.exe) 的文件。
FFMPEG_URLS = {
    ("darwin", "amd64"): ["https://www.osxexperts.net/ffmpeg80intel.zip"],
    ("darwin", "arm64"): ["https://www.osxexperts.net/ffmpeg80arm.zip"],
    ("windows", "amd64"): [
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    ],
}

DOWNLOAD_ATTEMPTS = 5


def download_bytes(url: str, attempts: int = DOWNLOAD_ATTEMPTS) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        print(f"downloading {url} (attempt {attempt}/{attempts})")
        try:
            resp = httpx.get(
                url, follow_redirects=True, timeout=httpx.Timeout(180.0, connect=30.0)
            )
            resp.raise_for_status()
            return resp.content
        except (httpx.HTTPError, httpx.StreamError) as exc:
            last = exc
            if attempt == attempts:
                break
            delay = min(2**attempt, 30)
            print(f"  failed: {exc!r}; retrying in {delay}s")
            time.sleep(delay)
    raise RuntimeError(f"download failed after {attempts} attempts: {url}") from last


def resolve_ffmpeg_urls(goos: str, goarch: str) -> list[str]:
    key = (goos, goarch)
    if key not in FFMPEG_URLS:
        raise KeyError(f"unsupported target for ffmpeg URL: {goos}/{goarch}")
    return FFMPEG_URLS[key]


def fetch_ffmpeg_zip(goos: str, goarch: str) -> bytes:
    errors: list[str] = []
    for url in resolve_ffmpeg_urls(goos, goarch):
        try:
            data = download_bytes(url)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        if zipfile.is_zipfile(io.BytesIO(data)):
            return data
        errors.append(f"{url}: response is not a zip archive ({len(data)} bytes)")
    raise RuntimeError("all ffmpeg mirrors failed:\n  " + "\n  ".join(errors))


def copy_ffmpeg(stage_dir: Path, goos: str, goarch: str):
    data = fetch_ffmpeg_zip(goos, goarch)
    ffmpeg_name = "ffmpeg.exe" if goos == "windows" else "ffmpeg"
    ffmpeg_path = stage_dir / ffmpeg_name

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if Path(name).name == ffmpeg_name:
                ffmpeg_path.write_bytes(zf.read(name))
                break
        else:
            raise FileNotFoundError(f"{ffmpeg_name} not found in zip archive")

    ffmpeg_path.chmod(0o755)


def package(binary_path: Path, out_path: Path, goos: str, goarch: str):
    if not binary_path.exists():
        raise FileNotFoundError(binary_path)

    with tempfile.TemporaryDirectory(prefix="sona-package-") as td:
        stage_dir = Path(td) / "bundle"
        stage_dir.mkdir(parents=True, exist_ok=True)

        binary_name = "sona.exe" if goos == "windows" else "sona"
        target_binary = stage_dir / binary_name
        shutil.copy2(binary_path, target_binary)
        target_binary.chmod(0o755)

        copy_ffmpeg(stage_dir, goos, goarch)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if goos == "windows":
            with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for item in sorted(stage_dir.iterdir()):
                    zf.write(item, arcname=item.name)
        else:
            with tarfile.open(out_path, "w:gz") as tar:
                for item in sorted(stage_dir.iterdir()):
                    tar.add(item, arcname=item.name)

    print(f"packaged {out_path} ({out_path.stat().st_size // 1024} KB)")


def main():
    parser = argparse.ArgumentParser(description="Package Sona release archive")
    parser.add_argument("--binary", required=True, help="Built sona binary path")
    parser.add_argument("--goos", required=True, choices=["darwin", "windows"])
    parser.add_argument("--goarch", required=True, choices=["amd64", "arm64"])
    parser.add_argument(
        "--out", required=True, help="Output archive path (.tar.gz or .zip)"
    )
    args = parser.parse_args()

    package(Path(args.binary), Path(args.out), args.goos, args.goarch)


if __name__ == "__main__":
    main()
