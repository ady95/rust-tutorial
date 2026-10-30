//! mdtoc: Markdown 문서의 제목으로 목차를 만든다 (python_src/mdtoc.py 의 Rust 이식).

mod tables;

use std::collections::{HashMap, HashSet};
use std::ffi::OsString;
use std::fs;
use std::io::{Read, Write};
use std::process::exit;

const USAGE: &str =
    "usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [--numbered] [file]";

fn in_ranges(table: &[(u32, u32)], c: char) -> bool {
    let cp = c as u32;
    table
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

/// Python `str.isspace()` 가 참인 글자 (`str.strip()` 이 지우는 글자).
fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\t'..='\r'
            | '\x1c'..='\x1f'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

fn py_strip(s: &str) -> &str {
    s.trim_matches(is_py_space)
}

/// Python `str.splitlines()` (keepends 없이).
fn split_lines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let bytes = text.as_bytes();
    let mut start = 0;
    let mut iter = text.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        if matches!(
            c,
            '\n' | '\r'
                | '\x0b'
                | '\x0c'
                | '\x1c'
                | '\x1d'
                | '\x1e'
                | '\u{85}'
                | '\u{2028}'
                | '\u{2029}'
        ) {
            lines.push(&text[start..i]);
            let mut end = i + c.len_utf8();
            if c == '\r' && bytes.get(end) == Some(&b'\n') {
                iter.next();
                end += 1;
            }
            start = end;
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// Python `str.lower()`: 전체 유니코드 규칙(İ 는 두 글자, 끝 시그마 문맥 포함)을 Python 3.12 기준 표로 따른다.
fn py_lower(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len());
    for (i, &c) in chars.iter().enumerate() {
        match c {
            '\u{3a3}' => out.push(if final_sigma(&chars, i) {
                '\u{3c2}'
            } else {
                '\u{3c3}'
            }),
            '\u{130}' => out.push_str("i\u{307}"),
            _ => match tables::LOWER.binary_search_by_key(&(c as u32), |&(from, _)| from) {
                Ok(idx) => out.push(char::from_u32(tables::LOWER[idx].1).unwrap_or(c)),
                Err(_) => out.push(c),
            },
        }
    }
    out
}

fn final_sigma(chars: &[char], i: usize) -> bool {
    let before = chars[..i]
        .iter()
        .rev()
        .find(|&&c| !in_ranges(tables::SIGMA_SKIP, c))
        .is_some_and(|&c| in_ranges(tables::SIGMA_CASED, c));
    let after = chars[i + 1..]
        .iter()
        .find(|&&c| !in_ranges(tables::SIGMA_SKIP, c))
        .is_some_and(|&c| in_ranges(tables::SIGMA_CASED, c));
    before && !after
}

fn count_leading_spaces(line: &str) -> usize {
    line.bytes().take_while(|&b| b == b' ').count()
}

/// 코드 블록 표시줄이면 (글자, 개수, 나머지)를 돌려준다.
fn fence_match(line: &str) -> Option<(char, usize, &str)> {
    let spaces = count_leading_spaces(line);
    if spaces > 3 {
        return None;
    }
    let rest = &line[spaces..];
    let ch = rest.chars().next()?;
    if ch != '`' && ch != '~' {
        return None;
    }
    let run = rest.chars().take_while(|&c| c == ch).count();
    if run < 3 {
        return None;
    }
    Some((ch, run, &rest[run..]))
}

/// 제목 줄이면 (수준, 제목 문자열)을 돌려준다. 제목 문자열은 아직 닫는 `#` 처리 전이다.
fn heading_match(line: &str) -> Option<(usize, &str)> {
    let spaces = count_leading_spaces(line);
    if spaces > 3 {
        return None;
    }
    let rest = &line[spaces..];
    let level = rest.bytes().take_while(|&b| b == b'#').count();
    if !(1..=6).contains(&level) {
        return None;
    }
    let after = &rest[level..];
    if after.is_empty() {
        return Some((level, ""));
    }
    if after.starts_with([' ', '\t']) {
        return Some((level, after.trim_start_matches([' ', '\t'])));
    }
    None
}

/// 끝의 닫는 `#` 묶음을 지우고 앞뒤 공백을 지운다.
fn clean_title(raw: &str) -> &str {
    let trimmed = raw.trim_end_matches([' ', '\t']);
    let without_hashes = trimmed.trim_end_matches('#');
    let t = if without_hashes.len() == trimmed.len() {
        raw
    } else if without_hashes.is_empty() {
        ""
    } else if without_hashes.ends_with([' ', '\t']) {
        without_hashes.trim_end_matches([' ', '\t'])
    } else {
        raw
    };
    py_strip(t)
}

fn headings(text: &str) -> Vec<(usize, String)> {
    let mut found = Vec::new();
    let mut fence: Option<(char, usize)> = None;
    for line in split_lines(text) {
        let m = fence_match(line);
        if let Some((fch, flen)) = fence {
            if let Some((ch, run, rest)) = m {
                if ch == fch && run >= flen && rest.trim_matches([' ', '\t']).is_empty() {
                    fence = None;
                }
            }
            continue;
        }
        if let Some((ch, run, rest)) = m {
            if !(ch == '`' && rest.contains('`')) {
                fence = Some((ch, run));
                continue;
            }
        }
        if let Some((level, raw)) = heading_match(line) {
            let title = clean_title(raw);
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
        .filter(|&c| c == '-' || c == ' ' || in_ranges(tables::WORD, c))
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
    let mut counters = [0usize; 7];
    let mut out = String::new();
    for e in entries {
        let depth = e.level - min_level;
        counters[depth] += 1;
        for c in counters.iter_mut().skip(depth + 1) {
            *c = 0;
        }
        out.push_str(&"   ".repeat(depth));
        out.push_str(&format!("{}. [{}](#{})\n", counters[depth], e.text, e.slug));
    }
    out
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

// ---- 명령줄 (argparse 동작을 따른다) ----

struct Args {
    file: OsString,
    min_level: usize,
    max_level: usize,
    json: bool,
    numbered: bool,
}

fn usage_error(msg: &str) -> ! {
    eprintln!("{USAGE}\nmdtoc: error: {msg}");
    exit(2);
}

fn digit_value(c: char) -> Option<u32> {
    let cp = c as u32;
    let idx = tables::DIGIT.binary_search_by(|&(lo, hi)| {
        if cp < lo {
            std::cmp::Ordering::Greater
        } else if cp > hi {
            std::cmp::Ordering::Less
        } else {
            std::cmp::Ordering::Equal
        }
    });
    idx.ok().map(|i| (cp - tables::DIGIT[i].0) % 10)
}

/// Python `int(str)` (10진수). 실패하면 None, 너무 큰 값은 상한으로 눌러 둔다.
fn py_int(s: &str) -> Option<i64> {
    let s = py_strip(s);
    let (neg, digits) = match s.strip_prefix('-') {
        Some(r) => (true, r),
        None => (false, s.strip_prefix('+').unwrap_or(s)),
    };
    if digits.is_empty() {
        return None;
    }
    let mut value: i64 = 0;
    let mut prev_digit = false;
    for c in digits.chars() {
        if c == '_' {
            if !prev_digit {
                return None;
            }
            prev_digit = false;
        } else {
            let d = digit_value(c)?;
            value = value
                .saturating_mul(10)
                .saturating_add(i64::from(d))
                .min(1_000_000);
            prev_digit = true;
        }
    }
    if !prev_digit {
        return None;
    }
    Some(if neg { -value } else { value })
}

fn is_negative_number(a: &str) -> bool {
    let Some(rest) = a.strip_prefix('-') else {
        return false;
    };
    let all_digits = |s: &str| s.chars().all(|c| digit_value(c).is_some());
    match rest.split_once('.') {
        Some((int, frac)) => all_digits(int) && !frac.is_empty() && all_digits(frac),
        None => !rest.is_empty() && all_digits(rest),
    }
}

enum Tok<'a> {
    Positional,
    Option(&'a str, Option<&'a str>),
    Unknown,
}

fn classify(a: &str) -> Tok<'_> {
    const KNOWN: [&str; 5] = [
        "--min-level",
        "--max-level",
        "--json",
        "--numbered",
        "--help",
    ];
    if !a.starts_with('-') {
        return Tok::Positional;
    }
    if KNOWN.contains(&a) || a == "-h" {
        return Tok::Option(a, None);
    }
    if a.len() == 1 {
        return Tok::Positional;
    }
    if let Some((opt, value)) = a.split_once('=') {
        if KNOWN.contains(&opt) || opt == "-h" {
            return Tok::Option(opt, Some(value));
        }
    }
    if !a.starts_with("--") && a.starts_with("-h") {
        return Tok::Option("-h", None);
    }
    if is_negative_number(a) || a.contains(' ') {
        return Tok::Positional;
    }
    Tok::Unknown
}

fn level_value(name: &str, raw: &str) -> usize {
    match py_int(raw) {
        Some(n) if (1..=6).contains(&n) => n as usize,
        _ => usage_error(&format!(
            "argument {name}: invalid choice: {raw:?} (choose from 1, 2, 3, 4, 5, 6)"
        )),
    }
}

/// `raw` 는 `argv` 와 같은 인자의 원본이다(UTF-8 이 아닌 파일 이름을 그대로 열기 위해).
fn parse_args(argv: &[String], raw: &[OsString]) -> Args {
    let mut args = Args {
        file: OsString::from("-"),
        min_level: 1,
        max_level: 6,
        json: false,
        numbered: false,
    };
    let mut file: Option<usize> = None;
    let mut bad: Option<String> = None;
    // argparse 는 옵션을 사이에 두고 이미 위치 인자를 받은 뒤에 오는 `--` 를 인식하지 못해 오류로 본다.
    let mut option_after_file = false;
    let mut i = 0;
    while i < argv.len() {
        let a = argv[i].as_str();
        i += 1;
        if a == "--" {
            if option_after_file {
                bad.get_or_insert_with(|| String::from("unrecognized arguments: --"));
            }
            for (k, rest) in argv.iter().enumerate().skip(i) {
                if file.is_some() {
                    bad.get_or_insert_with(|| format!("unrecognized arguments: {rest}"));
                } else {
                    file = Some(k);
                }
            }
            break;
        }
        match classify(a) {
            Tok::Positional => {
                if file.is_some() {
                    bad.get_or_insert_with(|| format!("unrecognized arguments: {a}"));
                } else {
                    file = Some(i - 1);
                }
            }
            Tok::Unknown => {
                bad.get_or_insert_with(|| format!("unrecognized arguments: {a}"));
            }
            Tok::Option(opt, explicit) => {
                option_after_file |= file.is_some();
                match opt {
                    "-h" | "--help" => {
                        if explicit.is_some() {
                            usage_error(&format!(
                                "argument -h/--help: ignored explicit argument {:?}",
                                explicit.unwrap_or("")
                            ));
                        }
                        println!("{USAGE}\n\nMake a table of contents from Markdown headings.");
                        exit(0);
                    }
                    "--json" | "--numbered" => {
                        if explicit.is_some() {
                            usage_error(&format!(
                                "argument {opt}: ignored explicit argument {:?}",
                                explicit.unwrap_or("")
                            ));
                        }
                        if opt == "--json" {
                            args.json = true;
                        } else {
                            args.numbered = true;
                        }
                    }
                    _ => {
                        let raw = match explicit {
                            Some(v) => v,
                            None => match argv.get(i).map(|n| (n.as_str(), classify(n))) {
                                Some((n, Tok::Positional)) if n != "--" => {
                                    i += 1;
                                    n
                                }
                                _ => usage_error(&format!("argument {opt}: expected one argument")),
                            },
                        };
                        let level = level_value(opt, raw);
                        if opt == "--min-level" {
                            args.min_level = level;
                        } else {
                            args.max_level = level;
                        }
                    }
                }
            }
        }
    }
    if let Some(msg) = bad {
        usage_error(&msg);
    }
    if let Some(k) = file {
        args.file = raw[k].clone();
    }
    if args.min_level > args.max_level {
        usage_error("--min-level must not be greater than --max-level");
    }
    args
}

fn main() {
    let raw: Vec<OsString> = std::env::args_os().skip(1).collect();
    let argv: Vec<String> = raw
        .iter()
        .map(|a| a.to_string_lossy().into_owned())
        .collect();
    let args = parse_args(&argv, &raw);
    let lossy = args.file.to_string_lossy().into_owned();
    let name = if args.file == "-" { "<stdin>" } else { &lossy };
    let read = if args.file == "-" {
        let mut buf = Vec::new();
        std::io::stdin().lock().read_to_end(&mut buf).map(|_| buf)
    } else {
        fs::read(&args.file)
    };
    let data = match read {
        Ok(d) => d,
        Err(err) => {
            let msg = err.to_string();
            let msg = msg.split(" (os error").next().unwrap_or("");
            eprintln!("mdtoc: error: cannot read {name}: {msg}");
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
    let mut stdout = std::io::stdout().lock();
    let _ = stdout.write_all(out.as_bytes());
    let _ = stdout.flush();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn slugs(text: &str) -> Vec<String> {
        build(text, 1, 6).into_iter().map(|e| e.slug).collect()
    }

    #[test]
    fn duplicate_anchors_do_not_collide() {
        assert_eq!(
            slugs("# A\n## a\n# a-1\n# a\n"),
            ["a", "a-1", "a-1-1", "a-2"]
        );
    }

    #[test]
    fn dotted_i_and_final_sigma() {
        assert_eq!(py_lower("İstanbul"), "i\u{307}stanbul");
        assert_eq!(py_lower("ΑΣ"), "ας");
        assert_eq!(slugs("# İstanbul\n"), ["istanbul"]);
    }

    #[test]
    fn splitlines_boundaries() {
        assert_eq!(split_lines("a\r\nb\rc\u{2028}d\n"), ["a", "b", "c", "d"]);
    }

    #[test]
    fn closing_hashes_and_fences() {
        let found = headings("## a ##  \n# b#\n```\n# no\n```\n#\n# ###\n");
        let titles: Vec<&str> = found.iter().map(|(_, t)| t.as_str()).collect();
        assert_eq!(titles, ["a", "b#"]);
    }

    #[test]
    fn numbered_resets_deeper_counters() {
        let e = build("# D\n### E\n# F\n### G\n", 1, 6);
        assert_eq!(
            render_numbered(&e, 1),
            "1. [D](#d)\n      1. [E](#e)\n2. [F](#f)\n      1. [G](#g)\n"
        );
    }
}
