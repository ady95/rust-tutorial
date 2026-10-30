"""Execute CLI, raw Unix argv/path, integer limit and output-failure differential checks."""
import contextlib, importlib.util, io, itertools, json, os, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',ROOT/'python_src/mdtoc.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
BIN=ROOT/'rust_app/target/release/mdtoc'
ENV={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
results={}
def run(args,python=False,**kw):
    cmd=[sys.executable,str(ROOT/'python_src/mdtoc.py')] if python else [str(BIN)]
    return subprocess.run(cmd+args,input=b'# A\n',capture_output=True,env=ENV,**kw)
def outcome(p):return (p.returncode,p.stdout)
def parse(args):
    with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        try:return ref.parse_args(args)
        except SystemExit as e:return e.code

def main():
    tokens=['--json','--numbered','--min-level','--max-level','--min-level=2','--max-level=3','--json=x','--js','--','-','1','2','7','-1','-h','--help','-hh','-hx','file','']
    mismatches=[];total=0
    for n in range(4):
        for args in itertools.product(tokens,repeat=n):
            expected=parse(list(args));p=run(list(args));total+=1
            if isinstance(expected,int): ok=p.returncode==expected and (expected==0 or not p.stdout)
            else:
                if expected.file=='-':
                    entries=ref.build('# A\n',expected.min_level,expected.max_level)
                    output=(json.dumps(entries,ensure_ascii=False)+'\n') if expected.json else (ref.render_numbered(entries,expected.min_level) if expected.numbered else ref.render(entries,expected.min_level))
                    ok=outcome(p)==(0,output.encode())
                else:ok=p.returncode==1 and not p.stdout
            if not ok:
                mismatches.append({'args':args,'python':expected if isinstance(expected,int) else vars(expected),'rust_code':p.returncode,'rust_stdout':p.stdout.decode(errors='backslashreplace')})
    assert all(x['python']==0 and x['rust_code']==2 for x in mismatches), 'Unexpected CLI mismatch beyond help/error precedence conflicts'
    results['cli']={'cases':total,'mismatches':mismatches}
    ints=[]
    for length in [1,2,639,640,641,4299,4300,4301,5000,10000]:
        for digit in ['0','٠','０']:
            for sep in ['', '_']:
                s=sep.join([digit]*(length-1)+['1'])
                py=run(['--min-level',s],True);rs=run(['--min-level',s])
                ints.append({'length':length,'digit':digit,'separator':sep,'python':py.returncode,'rust':rs.returncode,'match':outcome(py)==outcome(rs)})
    assert all(x['match'] or (x['length']>4300 and x['python']==2 and x['rust']==0) for x in ints)
    results['integers']=ints
    raw=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'verify') as temp:
        base=os.fsencode(temp)
        for b in range(1,256):
            if b==47:continue
            name=base+b'/name_'+bytes([b]);Path(os.fsdecode(name)).write_bytes(b'# raw\n')
            for args in [[name],[b'--',name],[b'-'+bytes([b])],[b'--min-level',bytes([b])]]:
                py=run(args,True);rs=run(args)
                if (py.returncode!=rs.returncode or (args!=[b'-h'] and py.stdout!=rs.stdout)):raw.append({'byte':b,'args':[repr(a) for a in args],'python':py.returncode,'rust':rs.returncode})
    assert not raw, raw
    results['raw_argv']={'cases':254*4,'mismatches':raw}
    output=[]
    for device in ['/dev/full','closed']:
        for python in [True,False]:
            cmd=[sys.executable,str(ROOT/'python_src/mdtoc.py')] if python else [str(BIN)]
            def closeout():os.close(1)
            with open('/dev/full','wb') as stream:
                p=subprocess.run(cmd,input=b'# A\n',stdout=stream if device=='/dev/full' else subprocess.DEVNULL,stderr=subprocess.PIPE,preexec_fn=closeout if device=='closed' else None,env=ENV)
            output.append({'device':device,'implementation':'python' if python else 'rust','code':p.returncode,'stderr':p.stderr.decode(errors='backslashreplace')})
    results['output_failure']=output
    Path(ROOT/'reports/edge_results.json').write_text(json.dumps(results,ensure_ascii=True,indent=2)+'\n')
    print('CLI:',total,'cases;',len(mismatches),'differences')
    print('Integer:',len(ints),'cases;',sum(not x['match'] for x in ints),'differences')
    print('Raw argv:',254*4,'cases;',len(raw),'differences')
    print('Output failures:',output)
if __name__=='__main__':main()
