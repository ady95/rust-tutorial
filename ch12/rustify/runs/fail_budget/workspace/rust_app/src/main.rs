//! mdtoc: Markdown 제목으로 목차를 만든다 (python_src/mdtoc.py 2판의 Rust 이식).

mod tables;

use std::collections::{HashMap, HashSet};
use std::ffi::OsString;
use std::io::{Read, Write};
use std::process::ExitCode;

const USAGE: &str =
    "usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [--numbered] [file]";

/// Python `str.isspace()` 와 같은 공백 판정(`str.strip()` 이 지우는 글자).
fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\t' | '\n'
            | '\u{0B}'
            | '\u{0C}'
            | '\r'
            | '\u{1C}'..='\u{20}'
            | '\u{85}'
            | '\u{A0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200A}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202F}'
            | '\u{205F}'
            | '\u{3000}'
    )
}

fn py_strip(s: &str) -> &str {
    s.trim_matches(is_py_space)
}

/// Python `re` 의 `\w` (isalnum 또는 `_`).
fn is_word(c: char) -> bool {
    if (c as u32) < 0x80 {
        return c.is_ascii_alphanumeric() || c == '_';
    }
    in_ranges(tables::WORD_RANGES, c)
}

fn in_ranges(ranges: &[(u32, u32)], c: char) -> bool {
    let c = c as u32;
    ranges
        .binary_search_by(|&(lo, hi)| {
            if c < lo {
                std::cmp::Ordering::Greater
            } else if c > hi {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

/// Python `str.lower()`. 표준 라이브러리는 유니코드 버전이 달라 Python 에서 만든 표를 쓴다.
fn py_lower(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len());
    for (i, &c) in chars.iter().enumerate() {
        if c.is_ascii() {
            out.push(c.to_ascii_lowercase());
        } else if c == '\u{3A3}' {
            let before = chars[..i]
                .iter()
                .rev()
                .find(|&&p| !in_ranges(tables::CASE_IGNORABLE, p))
                .is_some_and(|&p| in_ranges(tables::CASED, p));
            let after = chars[i + 1..]
                .iter()
                .find(|&&n| !in_ranges(tables::CASE_IGNORABLE, n))
                .is_some_and(|&n| in_ranges(tables::CASED, n));
            out.push(if before && !after {
                '\u{3C2}'
            } else {
                '\u{3C3}'
            });
        } else if let Ok(idx) = tables::LOWER.binary_search_by_key(&(c as u32), |&(k, _)| k) {
            out.push_str(tables::LOWER[idx].1);
        } else {
            out.push(c);
        }
    }
    out
}

/// 십진 숫자(Python `int()` 가 받는 글자)의 값.
fn digit_value(c: char) -> Option<u32> {
    let c = c as u32;
    let idx = tables::DIGIT_ZEROS.partition_point(|&z| z <= c);
    if idx == 0 {
        return None;
    }
    let d = c - tables::DIGIT_ZEROS[idx - 1];
    (d < 10).then_some(d)
}

/// Python `str.splitlines()`.
fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut iter = text.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        let is_break = matches!(
            c,
            '\n' | '\r'
                | '\u{0B}'
                | '\u{0C}'
                | '\u{1C}'
                | '\u{1D}'
                | '\u{1E}'
                | '\u{85}'
                | '\u{2028}'
                | '\u{2029}'
        );
        if !is_break {
            continue;
        }
        lines.push(&text[start..i]);
        start = i + c.len_utf8();
        if c == '\r' {
            if let Some(&(_, '\n')) = iter.peek() {
                iter.next();
                start += 1;
            }
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// FENCE 정규식: 앞 공백 0~3칸 뒤 같은 글자 3개 이상. (글자, 개수, 나머지)
fn match_fence(line: &str) -> Option<(char, usize, &str)> {
    let rest = line.trim_start_matches(' ');
    if line.len() - rest.len() > 3 {
        return None;
    }
    let ch = rest.chars().next()?;
    if ch != '`' && ch != '~' {
        return None;
    }
    let after = rest.trim_start_matches(ch);
    let n = rest.len() - after.len();
    (n >= 3).then_some((ch, n, after))
}

/// HEADING 정규식. (수준, 제목 문자열 원본)
fn match_heading(line: &str) -> Option<(usize, &str)> {
    let rest = line.trim_start_matches(' ');
    if line.len() - rest.len() > 3 {
        return None;
    }
    let after = rest.trim_start_matches('#');
    let level = rest.len() - after.len();
    if !(1..=6).contains(&level) {
        return None;
    }
    if after.is_empty() {
        return Some((level, ""));
    }
    let body = after.trim_start_matches([' ', '\t']);
    (body.len() != after.len()).then_some((level, body))
}

/// CLOSING 정규식을 지운다: 끝의 `#` 묶음(앞이 공백·탭이거나 전체가 `#`)과 뒤의 공백·탭.
fn strip_closing(s: &str) -> &str {
    let t = s.trim_end_matches([' ', '\t']);
    let before = t.trim_end_matches('#');
    if before.len() == t.len() {
        return s;
    }
    if before.is_empty() {
        return "";
    }
    let kept = before.trim_end_matches([' ', '\t']);
    if kept.len() == before.len() {
        s
    } else {
        kept
    }
}

fn headings(text: &str) -> Vec<(usize, String)> {
    let mut found = Vec::new();
    let mut fence: Option<(char, usize)> = None;
    for line in splitlines(text) {
        let m = match_fence(line);
        if let Some((fch, flen)) = fence {
            if let Some((ch, n, info)) = m {
                if ch == fch && n >= flen && info.trim_matches([' ', '\t']).is_empty() {
                    fence = None;
                }
            }
            continue;
        }
        if let Some((ch, n, info)) = m {
            if !(ch == '`' && info.contains('`')) {
                fence = Some((ch, n));
                continue;
            }
        }
        if let Some((level, body)) = match_heading(line) {
            let title = py_strip(strip_closing(body));
            if !title.is_empty() {
                found.push((level, title.to_string()));
            }
        }
    }
    found
}

fn slugify(title: &str, counts: &mut HashMap<String, usize>, used: &mut HashSet<String>) -> String {
    let base: String = py_lower(title)
        .chars()
        .filter(|&c| is_word(c) || c == '-' || c == ' ')
        .map(|c| if c == ' ' { '-' } else { c })
        .collect();
    let mut count = counts.get(&base).copied().unwrap_or(0);
    let mut slug = if count > 0 {
        format!("{base}-{count}")
    } else {
        base.clone()
    };
    while used.contains(&slug) {
        count += 1;
        slug = format!("{base}-{count}");
    }
    counts.insert(base, count + 1);
    used.insert(slug.clone());
    slug
}

struct Entry {
    level: usize,
    text: String,
    slug: String,
}

fn build(text: &str, min_level: usize, max_level: usize) -> Vec<Entry> {
    let mut counts = HashMap::new();
    let mut used = HashSet::new();
    let mut entries = Vec::new();
    for (level, title) in headings(text) {
        let slug = slugify(&title, &mut counts, &mut used);
        if (min_level..=max_level).contains(&level) {
            entries.push(Entry {
                level,
                text: title,
                slug,
            });
        }
    }
    entries
}

fn render(entries: &[Entry], min_level: usize) -> String {
    let mut out = String::new();
    for e in entries {
        out.push_str(&"  ".repeat(e.level - min_level));
        out.push_str(&format!("- [{}](#{})\n", e.text, e.slug));
    }
    out
}

fn render_numbered(entries: &[Entry], min_level: usize) -> String {
    let mut counters = [0usize; 6];
    let mut out = String::new();
    for e in entries {
        let depth = e.level - min_level;
        counters[depth] += 1;
        for c in &mut counters[depth + 1..] {
            *c = 0;
        }
        out.push_str(&"   ".repeat(depth));
        out.push_str(&format!("{}. [{}](#{})\n", counters[depth], e.text, e.slug));
    }
    out
}

/// Python `json.dumps(..., ensure_ascii=False)` 의 문자열 이스케이프.
fn json_string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0C}' => out.push_str("\\f"),
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

struct Options {
    file: Option<OsString>,
    min_level: usize,
    max_level: usize,
    json: bool,
    numbered: bool,
}

enum Parsed {
    Run(Options),
    Help,
    UsageError(String),
}

/// argparse 의 음수 모양 인자(`-5`, `-.5`, `-1.5`).
fn looks_negative_number(a: &str) -> bool {
    let Some(rest) = a.strip_prefix('-') else {
        return false;
    };
    let (int_part, frac) = match rest.split_once('.') {
        Some((i, f)) => (i, Some(f)),
        None => (rest, None),
    };
    let digits = |s: &str| s.chars().all(|c| digit_value(c).is_some());
    match frac {
        None => !int_part.is_empty() && digits(int_part),
        Some(f) => digits(int_part) && !f.is_empty() && digits(f),
    }
}

fn parse_level(s: &str) -> Option<usize> {
    let v = parse_int_value(s)?;
    (1..=6).contains(&v).then_some(v as usize)
}

/// 부호 없는 십진수와 부호를 해석해 값을 돌려준다(범위 비교용이라 큰 값은 포화).
fn parse_int_value(s: &str) -> Option<i64> {
    let s = py_strip(s);
    let (neg, digits) = match s.chars().next()? {
        '+' => (false, &s[1..]),
        '-' => (true, &s[1..]),
        _ => (false, s),
    };
    let mut value: i64 = 0;
    let mut prev_digit = false;
    let mut last_underscore = false;
    for c in digits.chars() {
        if c == '_' {
            if !prev_digit {
                return None;
            }
            prev_digit = false;
            last_underscore = true;
            continue;
        }
        let d = digit_value(c)?;
        value = value.saturating_mul(10).saturating_add(i64::from(d));
        prev_digit = true;
        last_underscore = false;
    }
    if !prev_digit || last_underscore {
        return None;
    }
    Some(if neg { -value } else { value })
}

fn parse_args(args: &[OsString]) -> Parsed {
    let mut opts = Options {
        file: None,
        min_level: 1,
        max_level: 6,
        json: false,
        numbered: false,
    };
    let mut extra = false;
    let mut after_dd = false;
    let mut i = 0;
    while i < args.len() {
        let raw = &args[i];
        let a = raw.to_string_lossy().into_owned();
        i += 1;
        let positional = after_dd || !a.starts_with('-') || a == "-";
        if positional {
            if opts.file.is_none() {
                opts.file = Some(raw.clone());
            } else {
                extra = true;
            }
            continue;
        }
        if a == "--" {
            after_dd = true;
            continue;
        }
        let (name, inline) = match a.split_once('=') {
            Some((n, v)) if a.starts_with("--") => (n.to_string(), Some(v.to_string())),
            _ => (a.clone(), None),
        };
        match name.as_str() {
            "-h" | "--help" => {
                if inline.is_some() && name == "--help" {
                    return Parsed::UsageError("ignored explicit argument".into());
                }
                return Parsed::Help;
            }
            "--json" | "--numbered" => {
                if inline.is_some() {
                    return Parsed::UsageError(format!(
                        "argument {name}: ignored explicit argument"
                    ));
                }
                if name == "--json" {
                    opts.json = true;
                } else {
                    opts.numbered = true;
                }
            }
            "--min-level" | "--max-level" => {
                let value = match inline {
                    Some(v) => v,
                    None => {
                        let Some(next) = args.get(i) else {
                            return Parsed::UsageError(format!(
                                "argument {name}: expected one argument"
                            ));
                        };
                        i += 1;
                        next.to_string_lossy().into_owned()
                    }
                };
                let Some(level) = parse_level(&value) else {
                    return Parsed::UsageError(format!(
                        "argument {name}: invalid value: '{value}'"
                    ));
                };
                if name == "--min-level" {
                    opts.min_level = level;
                } else {
                    opts.max_level = level;
                }
            }
            _ if !a.starts_with("--") && a.starts_with("-h") => return Parsed::Help,
            _ if looks_negative_number(&a) || a.contains(' ') => {
                if opts.file.is_none() {
                    opts.file = Some(raw.clone());
                } else {
                    extra = true;
                }
            }
            _ => extra = true,
        }
    }
    if extra {
        return Parsed::UsageError("unrecognized arguments".into());
    }
    if opts.min_level > opts.max_level {
        return Parsed::UsageError("--min-level must not be greater than --max-level".into());
    }
    Parsed::Run(opts)
}

fn run() -> u8 {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    let opts = match parse_args(&args) {
        Parsed::Run(o) => o,
        Parsed::Help => {
            println!("{USAGE}");
            return 0;
        }
        Parsed::UsageError(msg) => {
            eprintln!("{USAGE}\nmdtoc: error: {msg}");
            return 2;
        }
    };
    let file = opts.file.filter(|f| f != "-");
    let name = file.as_ref().map_or_else(
        || "<stdin>".to_string(),
        |f| f.to_string_lossy().into_owned(),
    );
    let mut data = Vec::new();
    let read = match &file {
        None => std::io::stdin().lock().read_to_end(&mut data).map(|_| ()),
        Some(path) => {
            std::fs::File::open(path).and_then(|mut fp| fp.read_to_end(&mut data).map(|_| ()))
        }
    };
    if let Err(err) = read {
        eprintln!("mdtoc: error: cannot read {name}: {err}");
        return 1;
    }
    let Ok(text) = String::from_utf8(data) else {
        eprintln!("mdtoc: error: {name}: not valid UTF-8");
        return 1;
    };
    let entries = build(&text, opts.min_level, opts.max_level);
    let output = if opts.json {
        render_json(&entries)
    } else if opts.numbered {
        render_numbered(&entries, opts.min_level)
    } else {
        render(&entries, opts.min_level)
    };
    let _ = std::io::stdout().lock().write_all(output.as_bytes());
    0
}

fn main() -> ExitCode {
    ExitCode::from(run())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dedupes_anchors() {
        let e = build("# A\n## a\n# a-1\n# a\n", 1, 6);
        let slugs: Vec<_> = e.iter().map(|e| e.slug.as_str()).collect();
        assert_eq!(slugs, ["a", "a-1", "a-1-1", "a-2"]);
    }

    #[test]
    fn closing_hashes() {
        assert_eq!(strip_closing("Title ##  "), "Title");
        assert_eq!(strip_closing("C#"), "C#");
        assert_eq!(strip_closing("###"), "");
    }

    #[test]
    fn splits_lines_like_python() {
        assert_eq!(splitlines("a\r\nb\rc\u{2028}d\n"), ["a", "b", "c", "d"]);
    }

    #[test]
    fn parses_ints() {
        assert_eq!(parse_level(" 3 "), Some(3));
        assert_eq!(parse_level("1_0"), None);
        assert_eq!(parse_level("7"), None);
        assert_eq!(parse_level("٣"), Some(3));
    }
}
