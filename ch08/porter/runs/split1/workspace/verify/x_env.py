"""검증자 환경 확인 (독립 검증, x_ 접두사 파일)."""
import os
import sys
import subprocess

print(sys.version)
print("uid", os.getuid(), "cpus", os.cpu_count())
for k in ("COLUMNS", "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING"):
    print(k, os.environ.get(k))
print("/dev/full writable:", os.access("/dev/full", os.W_OK))
try:
    fd = os.open("/dev/full", os.O_WRONLY)
    print("open /dev/full ok")
    os.close(fd)
except OSError as e:
    print("open /dev/full failed", e)
r = subprocess.run(["/home/dev/work/ch08_ws/split1/.venv/bin/python", "-c", "import sys,unicodedata;print(sys.version, unicodedata.unidata_version)"], capture_output=True)
print(r.stdout, r.stderr)
