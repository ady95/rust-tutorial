"""All permitted single filename bytes, malformed UTF-8 sequences and diagnostic escaping."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
count=0
with tempfile.TemporaryDirectory(dir=ROOT/'verify') as d:
    suffixes=[bytes([b]) for b in range(1,256) if b!=47]+[b'\xc0\xaf',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe2\x82',b'\x80\xc2\xa9\xff']
    for suffix in suffixes:
        filename=os.fsencode(d)+b'/raw_'+suffix
        for mode in ['valid','invalid','missing']:
            if mode=='missing':os.unlink(filename)
            else:
                with open(filename,'wb') as f:f.write(b'# Raw\n' if mode=='valid' else b'\xff')
            outputs=[]
            for cmd in [[sys.executable,str(ROOT/'python_src/mdtoc.py')],[str(ROOT/'rust_app/target/release/mdtoc')]]:
                p=subprocess.run(cmd+[filename],capture_output=True,env=env)
                outputs.append(p)
            py,rs=outputs
            assert (py.returncode,py.stdout)==(rs.returncode,rs.stdout),(repr(filename),mode,py,rs)
            if mode!='missing':assert py.stderr==rs.stderr,(repr(filename),mode,py.stderr,rs.stderr)
            else:
                label=os.fsdecode(filename).encode('utf-8','backslashreplace')
                assert rs.stderr.startswith(b'mdtoc: error: cannot read '+label+b': ')
                assert rs.stderr.endswith(b'\n')
            count+=1
print(f'PASS: {count} raw filename/read/UTF-8 error cases, including all 254 legal nonzero non-slash single bytes')
