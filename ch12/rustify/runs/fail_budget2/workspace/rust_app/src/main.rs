mod wordtab;

use std::collections::{HashMap, HashSet};
use std::io::{Read, Write};
use std::process::exit;

struct Args {
    file: String,
    min_level: usize,
    max_level: usize,
    json: bool,
    numbered: bool,
}

struct Entry {
    level: usize,
    text: String,
    slug: String,
}

fn usage_error(msg: &str) -> ! {
    eprintln!("usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [--numbered] [file]");
    eprintln!("mdtoc: error: {msg}");
    exit(2);
}

fn is_py_space(c: char) -> bool {
    matches!(c, '\t'..='\r' | '\x1c'..='\x1f' | ' ' | '\u{85}' | '\u{a0}' | '\u{1680}'
        | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}')
}

fn is_word(c: char) -> bool {
    let cp = c as u32;
    wordtab::WORD_RANGES
        .binary_search_by(|&(lo, hi)| {
            if cp < lo {
                std::cmp::Ordering::Greater
            } else if cp > hi {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

/// int() 가 받는 형식 중 ASCII 범위(공백, 부호, 밑줄 구분)를 해석한다.
fn parse_int(s: &str) -> Option<i64> {
    let t = s.trim_matches(is_py_space);
    let (neg, digits) = match t.strip_prefix('-') {
        Some(r) => (true, r),
        None => (false, t.strip_prefix('+').unwrap_or(t)),
    };
    if digits.is_empty() || digits.starts_with('_') || digits.ends_with('_') || digits.contains("__") {
        return None;
    }
    let mut v: i64 = 0;
    for c in digits.chars().filter(|&c| c != '_') {
        v = v.checked_mul(10)?.checked_add(i64::from(c.to_digit(10)?))?;
    }
    Some(if neg { -v } else { v })
}

fn level_value(opt: &str, val: &str) -> usize {
    match parse_int(val) {
        Some(n @ 1..=6) => n as usize,
        _ => usage_error(&format!("argument {opt}: invalid choice: {val}")),
    }
}

fn looks_negative_number(a: &str) -> bool {
    match a.strip_prefix('-') {
        Some(r) if !r.is_empty() => {
            let (i, f) = r.split_once('.').map_or((r, None), |(i, f)| (i, Some(f)));
            let digits = |s: &str| s.chars().all(|c| c.is_ascii_digit());
            match f {
                None => digits(i),
                Some(f) => digits(i) && !f.is_empty() && digits(f),
            }
        }
        _ => false,
    }
}

fn parse_args(argv: Vec<String>) -> Args {
    let mut args = Args { file: "-".into(), min_level: 1, max_level: 6, json: false, numbered: false };
    let mut file: Option<String> = None;
    let mut extra = false;
    let mut unknown = false;
    let mut only_positional = false;
    let mut it = argv.into_iter();
    while let Some(a) = it.next() {
        if only_positional || a == "-" || !a.starts_with('-') {
            if file.is_some() {
                extra = true;
            }
            file = Some(a);
            continue;
        }
        if a == "--" {
            only_positional = true;
            continue;
        }
        let (name, inline) = match a.split_once('=') {
            Some((n, v)) if n.starts_with("--") => (n, Some(v.to_string())),
            _ => (a.as_str(), None),
        };
        match name {
            "-h" | "--help" if inline.is_none() => {
                println!("usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [--numbered] [file]");
                exit(0);
            }
            "--json" | "--numbered" if inline.is_none() => {
                if name == "--json" {
                    args.json = true;
                } else {
                    args.numbered = true;
                }
            }
            "--min-level" | "--max-level" => {
                let val = match inline {
                    Some(v) => v,
                    None => match it.next() {
                        Some(v) if !v.starts_with('-') || v == "-" || looks_negative_number(&v) || v.contains(' ') => v,
                        _ => usage_error(&format!("argument {name}: expected one argument")),
                    },
                };
                let n = level_value(name, &val);
                if name == "--min-level" {
                    args.min_level = n;
                } else {
                    args.max_level = n;
                }
            }
            _ if looks_negative_number(&a) || a.contains(' ') => {
                if file.is_some() {
                    extra = true;
                }
                file = Some(a);
            }
            _ => unknown = true,
        }
    }
    if unknown || extra {
        usage_error("unrecognized arguments");
    }
    if let Some(f) = file {
        args.file = f;
    }
    if args.min_level > args.max_level {
        usage_error("--min-level must not be greater than --max-level");
    }
    args
}

fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = text.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        if matches!(c, '\n' | '\r' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}') {
            lines.push(&text[start..i]);
            start = i + c.len_utf8();
            if c == '\r' {
                if let Some(&(_, '\n')) = chars.peek() {
                    chars.next();
                    start += 1;
                }
            }
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// ` {0,3}(`{3,}|~{3,})(.*)` 에 해당: (표시 글자, 개수, 나머지)
fn fence_match(line: &str) -> Option<(char, usize, &str)> {
    let rest = line.trim_start_matches(' ');
    if line.len() - rest.len() > 3 {
        return None;
    }
    let c = rest.chars().next()?;
    if c != '`' && c != '~' {
        return None;
    }
    let n = rest.chars().take_while(|&x| x == c).count();
    if n < 3 {
        return None;
    }
    Some((c, n, &rest[n..]))
}

fn strip_closing(s: &str) -> &str {
    let t = s.trim_end_matches([' ', '\t']);
    let body = t.trim_end_matches('#');
    if body.len() == t.len() {
        return s;
    }
    if body.is_empty() {
        return "";
    }
    let before = body.trim_end_matches([' ', '\t']);
    if before.len() == body.len() {
        s
    } else {
        before
    }
}

fn headings(text: &str) -> Vec<(usize, String)> {
    let mut found = Vec::new();
    let mut fence: Option<(char, usize)> = None;
    for line in splitlines(text) {
        let m = fence_match(line);
        if let Some((fc, fnum)) = fence {
            if let Some((c, n, rest)) = m {
                if c == fc && n >= fnum && rest.trim_matches([' ', '\t']).is_empty() {
                    fence = None;
                }
            }
            continue;
        }
        if let Some((c, n, rest)) = m {
            if !(c == '`' && rest.contains('`')) {
                fence = Some((c, n));
                continue;
            }
        }
        let rest = line.trim_start_matches(' ');
        if line.len() - rest.len() > 3 {
            continue;
        }
        let level = rest.chars().take_while(|&c| c == '#').count();
        if !(1..=6).contains(&level) {
            continue;
        }
        let after = &rest[level..];
        if !after.is_empty() && !after.starts_with([' ', '\t']) {
            continue;
        }
        let title = strip_closing(after.trim_start_matches([' ', '\t'])).trim_matches(is_py_space);
        if !title.is_empty() {
            found.push((level, title.to_string()));
        }
    }
    found
}

fn slugify(title: &str, counts: &mut HashMap<String, usize>, used: &mut HashSet<String>) -> String {
    let base: String = title
        .to_lowercase()
        .chars()
        .filter(|&c| is_word(c) || c == '-' || c == ' ')
        .map(|c| if c == ' ' { '-' } else { c })
        .collect();
    let mut count = counts.get(&base).copied().unwrap_or(0);
    let mut slug = if count > 0 { format!("{base}-{count}") } else { base.clone() };
    while used.contains(&slug) {
        count += 1;
        slug = format!("{base}-{count}");
    }
    counts.insert(base, count + 1);
    used.insert(slug.clone());
    slug
}

fn build(text: &str, min_level: usize, max_level: usize) -> Vec<Entry> {
    let mut counts = HashMap::new();
    let mut used = HashSet::new();
    let mut entries = Vec::new();
    for (level, title) in headings(text) {
        let slug = slugify(&title, &mut counts, &mut used);
        if (min_level..=max_level).contains(&level) {
            entries.push(Entry { level, text: title, slug });
        }
    }
    entries
}

fn json_string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

fn render_json(entries: &[Entry]) -> String {
    let mut out = String::from("[");
    for (i, e) in entries.iter().enumerate() {
        if i > 0 {
            out.push_str(", ");
        }
        out.push_str(&format!("{{\"level\": {}, \"text\": ", e.level));
        json_string(&e.text, &mut out);
        out.push_str(", \"slug\": ");
        json_string(&e.slug, &mut out);
        out.push('}');
    }
    out.push_str("]\n");
    out
}

fn render(entries: &[Entry], min_level: usize) -> String {
    let mut out = String::new();
    for e in entries {
        out.push_str(&format!("{}- [{}](#{})\n", "  ".repeat(e.level - min_level), e.text, e.slug));
    }
    out
}

fn render_numbered(entries: &[Entry], min_level: usize) -> String {
    let mut counters = [0usize; 7];
    let mut out = String::new();
    for e in entries {
        let depth = e.level - min_level;
        counters[depth] += 1;
        for c in counters.iter_mut().skip(depth + 1) {
            *c = 0;
        }
        out.push_str(&format!("{}{}. [{}](#{})\n", "   ".repeat(depth), counters[depth], e.text, e.slug));
    }
    out
}

fn main() {
    let args = parse_args(std::env::args().skip(1).collect());
    let name = if args.file == "-" { "<stdin>".to_string() } else { args.file.clone() };
    let data = if args.file == "-" {
        let mut buf = Vec::new();
        std::io::stdin().read_to_end(&mut buf).map(|_| buf)
    } else {
        std::fs::read(&args.file)
    };
    let data = match data {
        Ok(d) => d,
        Err(err) => {
            eprintln!("mdtoc: error: cannot read {name}: {err}");
            exit(1);
        }
    };
    let Ok(text) = String::from_utf8(data) else {
        eprintln!("mdtoc: error: {name}: not valid UTF-8");
        exit(1);
    };
    let entries = build(&text, args.min_level, args.max_level);
    let out = if args.json {
        render_json(&entries)
    } else if args.numbered {
        render_numbered(&entries, args.min_level)
    } else {
        render(&entries, args.min_level)
    };
    let _ = std::io::stdout().write_all(out.as_bytes());
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dedupe_slugs() {
        let e = build("# A\n## a\n# a-1\n# a\n", 1, 6);
        let s: Vec<&str> = e.iter().map(|e| e.slug.as_str()).collect();
        assert_eq!(s, ["a", "a-1", "a-1-1", "a-2"]);
    }

    #[test]
    fn closing_hashes() {
        assert_eq!(headings("# foo ##\n#\n### ###\n# a#\n").len(), 2);
    }
}
