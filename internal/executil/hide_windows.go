//go:build windows

package executil

import (
	"os/exec"
	"syscall"
)

// HideWindow prevents a console flash when spawning CUI helpers (ffmpeg,
// sona-diarize) from a GUI host that itself was started with CREATE_NO_WINDOW.
func HideWindow(cmd *exec.Cmd) {
	if cmd.SysProcAttr == nil {
		cmd.SysProcAttr = &syscall.SysProcAttr{}
	}
	cmd.SysProcAttr.HideWindow = true
}
