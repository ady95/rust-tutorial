"""Compare every Unicode scalar in headings, including contextual sigma, to Python."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',ROOT/'python_src/mdtoc.py')
ref=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
binary=ROOT/'rust_app/target/release/mdtoc'
count=0
for start in range(0,0x110000,2048):
    chars=[chr(n) for n in range(start,min(start+2048,0x110000)) if not 0xD800<=n<=0xDFFF]
    text=''.join('# A'+c+'Σ AΣ'+c+'A '+c+'Z\n' for c in chars)
    expected=ref.build(text,1,6)
    actual=subprocess.run([str(binary),'--json'],input=text.encode(),capture_output=True,check=True)
    got=json.loads(actual.stdout)
    if got!=expected:
        for i,(a,b) in enumerate(zip(got,expected)):
            if a!=b: raise AssertionError((hex(start),i,a,b))
        raise AssertionError((hex(start),len(got),len(expected)))
    count+=len(chars)
print(f'PASS: {count} Unicode scalars; word membership, lowercase, contextual sigma, whitespace and heading parsing')
for value in ['١','２','+३','0_4','_1','1_','1__0','\x1c1',' 5 ','0006','-1','0','7','1.0']:
    args=['--min-level',value]
    py=subprocess.run([sys.executable,str(ROOT/'python_src/mdtoc.py'),*args],input=b'# A\n',capture_output=True)
    rs=subprocess.run([str(binary),*args],input=b'# A\n',capture_output=True)
    assert (py.returncode,py.stdout)==(rs.returncode,rs.stdout),(value,py,rs)
print('PASS: Unicode integer and malformed level arguments')
