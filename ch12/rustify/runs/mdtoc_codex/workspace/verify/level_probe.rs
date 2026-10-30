#[path="/home/dev/work/rustify_ws/mdtoc_codex/rust_app/src/unicode.rs"] mod unicode;
use std::collections::{HashMap, HashSet};
use std::io::{self, Read};
fn has(table: &[(u32, u32)], c: char) -> bool {
    table
        .binary_search_by(|&(a, b)| {
            if (c as u32) < a {
                std::cmp::Ordering::Greater
            } else if (c as u32) > b {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}
fn lower(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::new();
    for (i, &c) in chars.iter().enumerate() {
        if c == 'Σ' {
            let before = chars[..i]
                .iter()
                .rev()
                .find(|&&x| !has(unicode::IGNORABLE, x))
                .is_some_and(|&x| has(unicode::CASED, x));
            let after = chars[i + 1..]
                .iter()
                .find(|&&x| !has(unicode::IGNORABLE, x))
                .is_some_and(|&x| has(unicode::CASED, x));
            out.push(if before && !after { 'ς' } else { 'σ' });
        } else if let Ok(i) = unicode::LOWER.binary_search_by_key(&(c as u32), |x| x.0) {
            out.push_str(unicode::LOWER[i].1);
        } else {
            out.push(c);
        }
    }
    out
}
fn fence(line: &str) -> Option<(u8, usize, &str)> {
    let spaces = line.bytes().take_while(|&b| b == b' ').count();
    if spaces > 3 {
        return None;
    }
    let rest = &line[spaces..];
    let c = *rest.as_bytes().first()?;
    if c != b'`' && c != b'~' {
        return None;
    }
    let n = rest.bytes().take_while(|&b| b == c).count();
    (n >= 3).then_some((c, n, &rest[n..]))
}
fn title(line: &str) -> Option<(usize, String)> {
    let spaces = line.bytes().take_while(|&b| b == b' ').count();
    if spaces > 3 {
        return None;
    }
    let rest = &line[spaces..];
    let level = rest.bytes().take_while(|&b| b == b'#').count();
    if !(1..=6).contains(&level) {
        return None;
    }
    let rest = &rest[level..];
    if !rest.is_empty() && !rest.starts_with([' ', '\t']) {
        return None;
    }
    let t = rest.trim_start_matches([' ', '\t']);
    let end = t.trim_end_matches([' ', '\t']);
    let hashes = end.bytes().rev().take_while(|&b| b == b'#').count();
    let mut t = t;
    if hashes > 0 {
        let prefix = &end[..end.len() - hashes];
        if prefix.is_empty() || prefix.ends_with([' ', '\t']) {
            t = prefix.trim_end_matches([' ', '\t']);
        }
    }
    let t = t.trim_matches(|c| has(unicode::SPACE, c));
    (!t.is_empty()).then(|| (level, t.to_string()))
}
fn quote(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if c < ' ' => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
fn fail(message: &str, code: i32) -> ! {
    eprintln!("mdtoc: error: {message}");
    std::process::exit(code)
}
fn parse_level(s: &str) -> Option<usize> {
    let s = s.trim_matches(|c| has(unicode::SPACE, c) && !('\u{1c}'..='\u{1f}').contains(&c));
    let s = s.strip_prefix('+').unwrap_or(s);
    let mut value = 0usize;
    let mut digit = false;
    for c in s.chars() {
        if c == '_' && digit {
            digit = false;
            continue;
        }
        let d = unicode::DECIMAL
            .binary_search_by_key(&(c as u32), |x| x.0)
            .map(|i| unicode::DECIMAL[i].1 as usize)
            .ok()?;
        value = value.saturating_mul(10).saturating_add(d);
        digit = true;
    }
    if !digit || !(1..=6).contains(&value) {
        return None;
    }
    Some(value)
}
fn level(s: &str) -> usize {
    parse_level(s).unwrap_or_else(|| fail("invalid level", 2))
}
fn negative_number(s: &str) -> bool {
    let Some(s) = s.strip_prefix('-') else {
        return false;
    };
    let decimal = |c: char| {
        unicode::DECIMAL
            .binary_search_by_key(&(c as u32), |x| x.0)
            .is_ok()
    };
    if let Some((a, b)) = s.split_once('.') {
        a.chars().all(decimal) && !b.is_empty() && b.chars().all(decimal)
    } else {
        !s.is_empty() && s.chars().all(decimal)
    }
}
fn path_label(path: &std::ffi::OsStr) -> String {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        let mut bytes = path.as_bytes();
        let mut out = String::new();
        while !bytes.is_empty() {
            match std::str::from_utf8(bytes) {
                Ok(s) => {
                    out.push_str(s);
                    break;
                }
                Err(e) => {
                    out.push_str(std::str::from_utf8(&bytes[..e.valid_up_to()]).unwrap());
                    let end =
                        e.valid_up_to() + e.error_len().unwrap_or(bytes.len() - e.valid_up_to());
                    for b in &bytes[e.valid_up_to()..end] {
                        out.push_str(&format!("\\udc{b:02x}"));
                    }
                    bytes = &bytes[end..];
                }
            }
        }
        out
    }
    #[cfg(not(unix))]
    {
        path.to_string_lossy().into_owned()
    }
}
fn cli_main() {
    let mut min = 1;
    let mut max = 6;
    let mut json = false;
    let mut numbered = false;
    let mut file = None;
    let mut end = false;
    let mut option_after_file = false;
    let mut args = std::env::args_os().skip(1);
    while let Some(native_arg) = args.next() {
        let arg = native_arg.to_string_lossy().into_owned();
        if !end && arg == "--" {
            if option_after_file {
                fail("extra argument", 2);
            }
            end = true;
            continue;
        }
        if !end && file.is_some() && arg.starts_with('-') && arg != "-" && !negative_number(&arg) {
            option_after_file = true;
        }
        if !end && (arg == "--help" || arg == "-h") {
            println!("mdtoc [FILE] [--min-level N] [--max-level N] [--json] [--numbered]");
            return;
        }
        if !end && arg == "--json" {
            json = true;
            continue;
        }
        if !end && arg == "--numbered" {
            numbered = true;
            continue;
        }
        if !end
            && (arg == "--min-level"
                || arg == "--max-level"
                || arg.starts_with("--min-level=")
                || arg.starts_with("--max-level="))
        {
            let (key, value) = if let Some((k, v)) = arg.split_once('=') {
                (k.to_string(), v.to_string())
            } else {
                (
                    arg,
                    args.next()
                        .unwrap_or_else(|| fail("missing level", 2))
                        .to_string_lossy()
                        .into_owned(),
                )
            };
            let n = level(&value);
            if key == "--min-level" {
                min = n;
            } else {
                max = n;
            }
            continue;
        }
        if !end
            && arg.starts_with('-')
            && arg != "-"
            && !negative_number(&arg)
            && !arg.contains(' ')
        {
            fail("unknown option", 2);
        }
        if file.replace(native_arg).is_some() {
            fail("extra argument", 2);
        }
    }
    if min > max {
        fail("invalid level range", 2);
    }
    let file = file.unwrap_or_else(|| "-".into());
    let name = if file == "-" {
        "<stdin>".to_string()
    } else {
        path_label(&file)
    };
    let data = if file == "-" {
        let mut b = Vec::new();
        io::stdin().read_to_end(&mut b).map(|_| b)
    } else {
        std::fs::read(&file)
    }
    .unwrap_or_else(|e| fail(&format!("cannot read {name}: {e}"), 1));
    let text =
        String::from_utf8(data).unwrap_or_else(|_| fail(&format!("{name}: not valid UTF-8"), 1));
    let mut open = None;
    let mut counts = HashMap::new();
    let mut used = HashSet::new();
    let mut entries = Vec::new();
    for line in text.split([
        '\n', '\r', '\u{b}', '\u{c}', '\u{1c}', '\u{1d}', '\u{1e}', '\u{85}', '\u{2028}',
        '\u{2029}',
    ]) {
        let f = fence(line);
        if let Some((c, n)) = open {
            if f.is_some_and(|(fc, fn_, r)| {
                fc == c && fn_ >= n && r.trim_matches([' ', '\t']).is_empty()
            }) {
                open = None;
            }
            continue;
        }
        if let Some((c, n, r)) = f {
            if c != b'`' || !r.contains('`') {
                open = Some((c, n));
                continue;
            }
        }
        if let Some((l, t)) = title(line) {
            let base: String = lower(&t)
                .chars()
                .filter(|&c| has(unicode::WORD, c) || c == '-' || c == ' ')
                .map(|c| if c == ' ' { '-' } else { c })
                .collect();
            let n = counts.entry(base.clone()).or_insert(0usize);
            let mut slug = if *n == 0 {
                base.clone()
            } else {
                format!("{base}-{n}")
            };
            while used.contains(&slug) {
                *n += 1;
                slug = format!("{base}-{n}");
            }
            *n += 1;
            used.insert(slug.clone());
            if l >= min && l <= max {
                entries.push((l, t, slug));
            }
        }
    }
    if json {
        let rows: Vec<_> = entries
            .iter()
            .map(|(l, t, s)| {
                format!(
                    "{{\"level\": {l}, \"text\": {}, \"slug\": {}}}",
                    quote(t),
                    quote(s)
                )
            })
            .collect();
        println!("[{}]", rows.join(", "));
    } else {
        let mut counters = [0; 6];
        for (l, t, s) in entries {
            let d = l - min;
            if numbered {
                counters[d] += 1;
                counters[d + 1..].fill(0);
                println!("{}{}. [{t}](#{s})", " ".repeat(3 * d), counters[d]);
            } else {
                println!("{}- [{t}](#{s})", " ".repeat(2 * d));
            }
        }
    }
}

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
