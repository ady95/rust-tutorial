"""Exhaust bounded syntax strings and Unicode-context state combinations."""
import importlib.util,itertools,json,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',ROOT/'python_src/mdtoc.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
def check(lines):
    text='\n'.join(lines)+'\n'
    expected=ref.build(text,1,6)
    got=subprocess.run([str(ROOT/'rust_app/target/release/mdtoc'),'--json'],input=text.encode(),capture_output=True,check=True)
    assert json.loads(got.stdout)==expected
count=0;batch=[]
for n in range(7):
    for chars in itertools.product(' \t#`~A\x1f\u0301',repeat=n):
        batch.append(''.join(chars));count+=1
        if len(batch)==4096:check(batch);batch=[]
if batch:check(batch)
print(f'PASS: all {count} syntax strings of length 0..6 over eight boundary characters, as ordered documents')
# Representatives: cased, uncased, ignorable, cased+ignorable; sigma; multi-scalar lower.
count=0;batch=[]
for n in range(6):
    for chars in itertools.product(['A','1','\u0301','\u0345','Σ','İ'],repeat=n):
        batch.append('# x '+''.join(chars)+' y');count+=1
        if len(batch)==4096:check(batch);batch=[]
if batch:check(batch)
print(f'PASS: all {count} Unicode context strings of length 0..5 over six case-property representatives')
