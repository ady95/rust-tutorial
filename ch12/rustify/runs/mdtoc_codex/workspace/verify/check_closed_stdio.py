"""Execute contract-excluded closed standard streams and broken-pipe cases."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for case in ['stdin','stdout','stderr','broken-pipe']:
    for kind in ['python','rust']:
        cmd=[sys.executable,str(ROOT/'python_src/mdtoc.py')] if kind=='python' else [str(ROOT/'rust_app/target/release/mdtoc')]
        if case=='stderr':cmd+=['--unknown']
        kwargs={}
        if case=='broken-pipe':
            readfd,writefd=os.pipe();os.close(readfd);kwargs['stdout']=writefd
        else:
            fd={'stdin':0,'stdout':1,'stderr':2}[case]
            kwargs['preexec_fn']=lambda fd=fd:os.close(fd)
            kwargs['stdout']=subprocess.PIPE
        p=subprocess.run(cmd,input=b'# A\n',stderr=subprocess.PIPE,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},**kwargs)
        if case=='broken-pipe':os.close(writefd)
        rows.append({'case':case,'implementation':kind,'code':p.returncode,'stderr':p.stderr.decode(errors='backslashreplace')})
(ROOT/'reports/closed_stdio_results.json').write_text(json.dumps(rows,indent=2)+'\n')
for row in rows:print(row['case'],row['implementation'],row['code'])
