#!/bin/sh
cd /Volumes/work/Github/tools/st_plugin/MySideBar || exit 1
python3 -m py_compile mysidebar/batch/rollback.py mysidebar/batch/execute.py mysidebar/platform.py mysidebar/api.py > check_out.txt 2>&1
echo "COMPILE_EXIT=$?" >> check_out.txt
python3 _check.py >> check_out.txt 2>&1
echo "CHECK_EXIT=$?" >> check_out.txt