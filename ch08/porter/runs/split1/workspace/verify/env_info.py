"""Python 버전과 unicodedata 버전을 출력한다."""

import os
import sys
import unicodedata

print(sys.version)
print("unidata", unicodedata.unidata_version)
print("euid", os.geteuid())
