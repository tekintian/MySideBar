#!/bin/sh
PROJECT="/Volumes/work/Github/tools/st_plugin/MySideBar"
SRC="$PROJECT/src"
OUT="$PROJECT/tests/check_out.txt"

: > "$OUT"

cd "$SRC" || exit 1
find . -name "*.py" -not -path "*/__pycache__/*" -print > /tmp/mysidebar_py_list.txt
python3 -m py_compile $(cat /tmp/mysidebar_py_list.txt) >> "$OUT" 2>&1
COMPILE_RC=$?
echo "COMPILE_EXIT=$COMPILE_RC" >> "$OUT"

cd "$PROJECT" || exit 1
rm -rf /tmp/fake_packages
python3 tests/_smoke.py >> "$OUT" 2>&1
SMOKE_RC=$?
echo "SMOKE_EXIT=$SMOKE_RC" >> "$OUT"

python3 tests/_check.py >> "$OUT" 2>&1
CHECK_RC=$?
echo "CHECK_EXIT=$CHECK_RC" >> "$OUT"

python3 tests/_menu_roundtrip.py >> "$OUT" 2>&1
ROUNDTRIP_RC=$?
echo "ROUNDTRIP_EXIT=$ROUNDTRIP_RC" >> "$OUT"

python3 tests/_encoding_roundtrip.py >> "$OUT" 2>&1
ENCODING_RC=$?
echo "ENCODING_EXIT=$ENCODING_RC" >> "$OUT"

python3 tests/_encoding_detect.py >> "$OUT" 2>&1
DETECT_RC=$?
echo "DETECT_EXIT=$DETECT_RC" >> "$OUT"

python3 tests/_entry_export.py >> "$OUT" 2>&1
ENTRY_RC=$?
echo "ENTRY_EXIT=$ENTRY_RC" >> "$OUT"

python3 tests/_import_order.py >> "$OUT" 2>&1
IMPORT_RC=$?
echo "IMPORT_EXIT=$IMPORT_RC" >> "$OUT"

python3 tests/_listener_case.py >> "$OUT" 2>&1
LISTENER_RC=$?
echo "LISTENER_EXIT=$LISTENER_RC" >> "$OUT"

python3 tests/_listener_roundtrip.py >> "$OUT" 2>&1
LISTENER_RT_RC=$?
echo "LISTENER_RT_EXIT=$LISTENER_RT_RC" >> "$OUT"

TOTAL=0
for rc in "$COMPILE_RC" "$SMOKE_RC" "$CHECK_RC" "$ROUNDTRIP_RC" "$ENCODING_RC" "$DETECT_RC" "$ENTRY_RC" "$IMPORT_RC" "$LISTENER_RC" "$LISTENER_RT_RC"; do
	if [ "$rc" -ne 0 ]; then
		TOTAL=1
	fi
done
for marker in "failures " "ROUNDTRIP_FAILURES " "ENCODING_FAILURES " "DETECT_FAILURES " "ENTRY_FAILURES " "LISTENER_FAILURES " "LISTENER_RT_FAILURES "; do
	count=$(grep -h "^$marker" "$OUT" | tail -1 | awk '{print $NF}')
	if [ -n "$count" ] && [ "$count" -ne 0 ]; then
		TOTAL=1
	fi
done
echo "TOTAL_EXIT=$TOTAL" >> "$OUT"
exit "$TOTAL"