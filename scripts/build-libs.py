# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Build whisper.cpp static libs for the current platform and optionally upload to a GitHub release."""

import argparse, os, platform, shutil, subprocess, tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WHISPER_REPO = "https://github.com/ggml-org/whisper.cpp.git"


def run(*args: str, cwd: str | None = None):
    print(f"$ {' '.join(args)}")
    subprocess.run(args, cwd=cwd, check=True)


def get_whisper_commit() -> str:
    return (ROOT / ".whisper.cpp-commit").read_text().strip()


def platform_id() -> str:
    system = platform.system().lower()  # darwin, linux, windows
    machine = platform.machine().lower()  # arm64, x86_64, amd64
    return f"{system}-{machine}"


def clone(commit: str, src_dir: Path):
    if src_dir.exists():
        shutil.rmtree(src_dir)
    src_dir.mkdir(parents=True)
    run("git", "init", cwd=str(src_dir))
    run("git", "remote", "add", "origin", WHISPER_REPO, cwd=str(src_dir))
    run("git", "fetch", "--depth", "1", "origin", commit, cwd=str(src_dir))
    run("git", "checkout", "FETCH_HEAD", cwd=str(src_dir))
    run(
        "git",
        "submodule",
        "update",
        "--init",
        "--depth",
        "1",
        "--recursive",
        cwd=str(src_dir),
    )


def isa_flags() -> list[str]:
    """Pin the instruction set baseline the released libs are allowed to require.

    ggml defaults `GGML_NATIVE=ON`, which is `-march=native`: whatever CPU the CI
    runner happens to have is baked into libggml-*. GitHub's x64 runners are
    AVX-512 capable, so the v0.3.0 libs carried EVEX instructions and every CPU
    without AVX-512 (i9-9900K, AMD Ryzen up to Zen 3, most Xeons in the field)
    died with 0xC000001D (STATUS_ILLEGAL_INSTRUCTION) inside
    `whisper_init_from_buffer_with_params` / `ggml_backend_dev_count`.

    A static ggml-cpu has no runtime dispatch between ISA levels, so the floor
    has to be chosen here, once, and stated explicitly: a future CMake default
    change must not silently reintroduce the crash.
    """
    system = platform.system()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        # Haswell (2013)+. AVX-512 stays OFF: enabling it would re-break every
        # non-AVX512 CPU, because there is no per-function dispatch to fall back on.
        return [
            "-DGGML_NATIVE=OFF",
            "-DGGML_SSE42=ON",
            "-DGGML_AVX=ON",
            "-DGGML_AVX2=ON",
            "-DGGML_FMA=ON",
            "-DGGML_F16C=ON",
            "-DGGML_BMI2=ON",
            "-DGGML_AVX512=OFF",
        ]
    if machine in ("arm64", "aarch64"):
        if system == "Darwin":
            # M1 feature level: every Apple Silicon chip from M1 on supports it,
            # and it is what -march=native resolves to on the arm64 runner.
            return ["-DGGML_NATIVE=OFF", "-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16"]
        # Linux arm64 runners are Neoverse-class (SVE/SVE2); target the widest
        # baseline in use instead (Raspberry Pi 4 / Cortex-A72).
        return ["-DGGML_NATIVE=OFF", "-DGGML_CPU_ARM_ARCH=armv8-a"]
    # Unknown arch: at least never compile for the build machine.
    return ["-DGGML_NATIVE=OFF"]


def cmake_flags() -> list[str]:
    flags = [
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DWHISPER_BUILD_EXAMPLES=OFF",
        "-DWHISPER_BUILD_TESTS=OFF",
        "-DWHISPER_BUILD_SERVER=OFF",
    ]
    flags += isa_flags()
    system = platform.system()
    if system == "Darwin":
        flags += ["-DGGML_METAL=ON", "-DGGML_METAL_EMBED_LIBRARY=ON"]

        # Target macOS 12+ so Accelerate headers don't emit ILP64 BLAS symbols
        # (_cblas_sgemm$NEWLAPACK$ILP64) that don't exist before macOS 13.3.
        flags += ["-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0"]
    elif system in ("Linux", "Windows"):
        flags += ["-DGGML_VULKAN=ON"]
    if system == "Windows":
        flags += ["-G", "MinGW Makefiles"]
    return flags


def build(src_dir: Path, build_dir: Path):
    if build_dir.exists():
        shutil.rmtree(build_dir)
    run("cmake", "-S", str(src_dir), "-B", str(build_dir), *cmake_flags())
    jobs = str(os.cpu_count() or 4)
    run("cmake", "--build", str(build_dir), "--config", "Release", f"-j{jobs}")


def build_vulkan_delay_lib(build_dir: Path):
    """Create a delay-import library for vulkan-1.dll so sona doesn't crash on startup without Vulkan."""
    if platform.system() != "Windows":
        return
    delay_dir = build_dir / "delay"
    delay_dir.mkdir(exist_ok=True)
    # Find vulkan-1.dll in MinGW
    result = subprocess.run(["where", "vulkan-1.dll"], capture_output=True, text=True)
    if result.returncode != 0:
        # Try common MinGW path
        dll_path = "vulkan-1.dll"
    else:
        dll_path = result.stdout.strip().splitlines()[0]
    run("gendef", dll_path, cwd=str(delay_dir))
    run("dlltool", "--input-def", "vulkan-1.def", "--output-delaylib", "libvulkan-1-delay.a", cwd=str(delay_dir))


def verify_no_avx512(build_dir: Path):
    """Fail the build if a packaged lib carries AVX-512 instructions.

    These archives are linked into the app every user runs. One EVEX instruction
    reachable from model load is a hard crash (0xC000001D) on every CPU without
    AVX-512 — which is most CPUs. The grep is crude, but it is exactly the defect
    that shipped in v0.3.0, so it earns its place as a release gate.
    """
    if platform.machine().lower() not in ("x86_64", "amd64"):
        return
    objdump = shutil.which("objdump")
    if objdump is None:
        print("  warning: objdump not found — skipping the AVX-512 scan")
        return
    for name in lib_names():
        if name == "libvulkan-1-delay.a":
            continue
        lib, _ = find_lib(build_dir, name)
        # Stream: objdump on a full archive is hundreds of MB of text, and the
        # first hit already fails the build.
        proc = subprocess.Popen(
            [objdump, "-d", str(lib)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
        try:
            for line in proc.stdout:
                if "zmm" in line:
                    raise SystemExit(
                        f"{lib.name}: AVX-512 instruction found — refusing to package libs that "
                        f"crash on non-AVX512 CPUs. First hit: {line.strip()}"
                    )
        finally:
            proc.stdout.close()
            proc.wait()
    print("  AVX-512 scan: clean")


def lib_names() -> list[str]:
    common = ["libwhisper.a", "libggml.a", "libggml-base.a", "libggml-cpu.a"]
    system = platform.system()
    if system == "Darwin":
        common += ["libggml-metal.a", "libggml-blas.a"]
    elif system in ("Linux", "Windows"):
        common += ["libggml-vulkan.a"]
    if system == "Windows":
        common += ["libvulkan-1-delay.a"]
    return common


def find_lib(build_dir: Path, name: str) -> tuple[Path, str]:
    """Find a static lib by expected name (and Windows no-prefix fallback)."""
    candidates = [name]
    if platform.system() == "Windows" and name.startswith("lib"):
        candidates.append(name[3:])

    for candidate in candidates:
        for p in build_dir.rglob(candidate):
            return p, candidate
    raise FileNotFoundError(f"{name} not found under {build_dir}")


def package(build_dir: Path, src_dir: Path, archive: Path):
    pkg = build_dir / "pkg"
    if pkg.exists():
        shutil.rmtree(pkg)
    (pkg / "lib").mkdir(parents=True)
    (pkg / "include").mkdir(parents=True)
    for name in lib_names():
        lib, matched_name = find_lib(build_dir, name)
        print(f"  found {matched_name} at {lib} (packaged as {name})")
        # Normalize archive names so cgo -l<name> works consistently on every platform.
        shutil.copy2(lib, pkg / "lib" / name)
    shutil.copy2(src_dir / "include/whisper.h", pkg / "include/whisper.h")
    with tarfile.open(archive, "w:gz") as tar:
        for item in pkg.iterdir():
            tar.add(item, arcname=item.name)
    print(f"packaged {archive} ({archive.stat().st_size // 1024} KB)")


def upload(archive: Path, tag: str):
    import time

    # Release may already exist from another matrix job — ignore error
    subprocess.run(["gh", "release", "create", tag, "--generate-notes"], check=False)
    # Retry upload — release may take a moment to become available
    for attempt in range(5):
        result = subprocess.run(
            ["gh", "release", "upload", tag, str(archive), "--clobber"]
        )
        if result.returncode == 0:
            break
        print(f"upload attempt {attempt + 1} failed, retrying...")
        time.sleep(3)
    else:
        raise RuntimeError(f"failed to upload {archive.name} after 5 attempts")
    print(f"uploaded {archive.name} to release {tag}")


def main():
    parser = argparse.ArgumentParser(description="Build whisper.cpp static libs")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to GitHub release (tag derived from commit)",
    )
    args = parser.parse_args()

    commit = get_whisper_commit()
    plat = platform_id()
    src_dir = ROOT / "whisper-src"
    build_dir = ROOT / "whisper-build"
    archive = ROOT / f"whisper-libs-{plat}.tar.gz"

    print(f"commit: {commit}")
    print(f"platform: {plat}")

    clone(commit, src_dir)
    build(src_dir, build_dir)
    build_vulkan_delay_lib(build_dir)
    verify_no_avx512(build_dir)
    package(build_dir, src_dir, archive)

    if args.upload:
        tag = f"libraries-{commit[:7]}"
        upload(archive, tag)


if __name__ == "__main__":
    main()
