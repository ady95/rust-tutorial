"""Probe actual Rust level parser against Python int for every Unicode scalar."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'rust_app/src/main.rs').read_text()
source=source.replace('mod unicode;', '#[path="'+str(ROOT/'rust_app/src/unicode.rs')+'"] mod unicode;').replace('fn main() {','fn cli_main() {')
source+='''
fn main() {
    use std::io::Write;
    let mut out = Vec::new();
    for n in 0..=0x10ffff {
        if let Some(c) = char::from_u32(n) {
            for s in [c.to_string(), format!("{c}1{c}")] {
                out.push(parse_level(&s).unwrap_or(0) as u8);
            }
        }
    }
    std::io::stdout().write_all(&out).unwrap();
}
'''
probe=ROOT/'verify/level_probe.rs';probe.write_text(source)
subprocess.run(['rustc','--edition=2021','-O','-Awarnings',str(probe),'-o',str(ROOT/'verify/level_probe')],check=True)
data=subprocess.run([str(ROOT/'verify/level_probe')],capture_output=True,check=True).stdout
index=0
for n in range(0x110000):
    if 0xD800<=n<=0xDFFF:continue
    c=chr(n)
    for s in [c,c+'1'+c]:
        try:
            val=int(s)
            expected=val if 1<=val<=6 else 0
        except ValueError:expected=0
        assert data[index]==expected,(hex(n),repr(s),data[index],expected)
        index+=1
assert index==len(data)
print(f'PASS: {index} parser results; every Unicode scalar alone and around digit 1')
