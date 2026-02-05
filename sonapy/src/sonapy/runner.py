from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys


class SonaError(Exception):
    pass


class Runner:
    """Manages the ``sona`` child process lifecycle."""

    def __init__(self, port: int = 0) -> None:
        binary = shutil.which("sona")
        if binary is None:
            raise SonaError(
                "'sona' binary not found on PATH. "
                "Install it or add its location to PATH."
            )

        self._process = subprocess.Popen(
            [binary, "serve", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            line = self._process.stdout.readline()  # type: ignore[union-attr]
            if not line:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""  # type: ignore[union-attr]
                raise SonaError(f"sona exited before ready signal: {stderr}")
            info = json.loads(line)
            if info.get("status") != "ready":
                raise SonaError(f"unexpected ready signal: {info}")
            self.port: int = info["port"]
        except Exception:
            self._process.kill()
            raise

    @property
    def alive(self) -> bool:
        return self._process.poll() is None

    def stop(self) -> None:
        """Send SIGTERM and wait for clean shutdown."""
        if self._process.poll() is not None:
            return
        if sys.platform == "win32":
            self._process.terminate()
        else:
            self._process.send_signal(signal.SIGTERM)
        try:
            self._process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._process.kill()
