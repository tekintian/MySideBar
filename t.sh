#!/bin/bash
cd "$(dirname "$0")"
status=0
run() {
	local label="$1"
	shift
	echo "===== $label ====="
	"$@"
	local code=$?
	if [ "$code" -ne 0 ]; then
		status=1
	fi
}
run "encoding detect" python3 tests/_encoding_detect.py
run "i18n keys" python3 tests/_i18n_keys.py
run "menus and structure" python3 tests/_check.py
echo "===== SUMMARY ====="
if [ "$status" -eq 0 ]; then
	echo "ALL TESTS PASSED"
else
	echo "TESTS FAILED"
fi
exit "$status"