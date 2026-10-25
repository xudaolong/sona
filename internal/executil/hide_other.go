//go:build !windows

package executil

import "os/exec"

// HideWindow is a no-op outside Windows.
func HideWindow(cmd *exec.Cmd) {}
