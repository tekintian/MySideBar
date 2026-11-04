#!/bin/sh
cd /Volumes/work/Github/tools/st_plugin/MySideBar || exit 1
OUT=tests/check_out.txt
python3 -m py_compile MySideBar.py mysidebar/__init__.py mysidebar/platform.py mysidebar/api.py mysidebar/strings.py mysidebar/i18n.py mysidebar/batch/options.py mysidebar/batch/patterns.py mysidebar/batch/plan.py mysidebar/batch/execute.py mysidebar/batch/rollback.py mysidebar/ui/preview.py mysidebar/ui/preview_model.py mysidebar/cmds/clipboard.py mysidebar/cmds/encoding.py mysidebar/cmds/file_ops.py mysidebar/cmds/open.py mysidebar/cmds/search.py mysidebar/cmds/settings.py mysidebar/cmds/shadow.py mysidebar/cmds/tab.py mysidebar/cmds/trash_cmd.py mysidebar/cmds/batch_rename.py > "$OUT" 2>&1
echo "COMPILE_EXIT=$?" >> "$OUT"
rm -rf /tmp/fake_packages
python3 tests/_smoke.py >> "$OUT" 2>&1
echo "SMOKE_EXIT=$?" >> "$OUT"
python3 tests/_check.py >> "$OUT" 2>&1
echo "CHECK_EXIT=$?" >> "$OUT"