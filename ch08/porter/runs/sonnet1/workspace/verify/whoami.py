"""권한 시나리오(permission-denied)가 의미 있는지 보기 위해 실행 사용자와 chmod 0 파일 읽기 가능 여부를 출력한다."""

import os
import tempfile

print("uid", os.getuid())
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "s.txt")
    open(p, "w").write("x")
    os.chmod(p, 0)
    try:
        open(p).read()
        print("chmod 0 file is readable (permission scenario is NOT meaningful)")
    except PermissionError:
        print("chmod 0 file raises PermissionError (permission scenario is meaningful)")
    os.chmod(p, 0o600)
