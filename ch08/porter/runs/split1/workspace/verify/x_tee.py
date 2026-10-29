"""x_tee.py <log> <script.py> [args...]: 스크립트를 실행하며 stdout 을 verify/<log> 에도 남긴다."""
import os
import runpy
import sys


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
            st.flush()
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


here = os.path.dirname(os.path.abspath(__file__))
log = open(os.path.join(here, os.path.basename(sys.argv[1])), "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, log)
script = os.path.join(here, os.path.basename(sys.argv[2]))
sys.argv = [script] + sys.argv[3:]
sys.path.insert(0, here)
runpy.run_path(script, run_name="__main__")
