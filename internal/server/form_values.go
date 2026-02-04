package server

import "strconv"

func parseBoolFormValue(v string) bool {
	b, err := strconv.ParseBool(v)
	return err == nil && b
}
