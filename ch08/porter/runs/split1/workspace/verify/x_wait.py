"""verify/<log> 에 'diffs' 줄이 나올 때까지 기다린 뒤 내용을 출력 (최대 580초)."""
import os
import sys
import time

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.basename(sys.argv[1]))
end = time.time() + 580
while time.time() < end:
    with open(p, encoding="utf-8") as fp:
        text = fp.read()
    if "diffs" in text:
        break
    time.sleep(10)
print(text[:20000])
