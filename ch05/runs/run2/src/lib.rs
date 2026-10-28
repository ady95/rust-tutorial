//! wordfreq: 텍스트의 단어 빈도를 세는 로직 (python_src/wordfreq.py 의 Rust 이식).
//!
//! 동작 계약은 contracts/behavior_spec.md 에 있다. 이 모듈은 파일과 표준 입출력에 접근하지 않는다.

use std::collections::HashMap;
use std::ffi::OsString;
use std::fmt::Write as _;

pub const EXIT_OK: u8 = 0;
pub const EXIT_INPUT_ERROR: u8 = 1;
pub const EXIT_USAGE_ERROR: u8 = 2;

pub const DEFAULT_TOP: usize = 10;

pub const USAGE: &str = "usage: wordfreq FILE [--top N] [--json]";

pub const HELP: &str = "\
usage: wordfreq FILE [--top N] [--json]

Count word frequencies.

arguments:
  FILE        UTF-8 text file
  --top N     number of words (default 10)
  --json      print JSON instead of text
  -h, --help  show this help message and exit
";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, usize)>,
}

/// Python `str.split()` 의 공백 (계약 2절 2항).
/// Rust 의 White_Space 에 Python 이 공백으로 보는 U+001C..U+001F 를 더한 것과 같다.
fn is_python_whitespace(c: char) -> bool {
    c.is_whitespace() || matches!(c, '\u{1C}'..='\u{1F}')
}

/// 단어 앞뒤에서 떼어 낼 문장 부호: ASCII 문장 부호 32자 + “ ” ‘ ’ … · (계약 2절 3항).
fn is_punctuation(c: char) -> bool {
    c.is_ascii_punctuation() || matches!(c, '“' | '”' | '‘' | '’' | '…' | '·')
}

/// 기준 Python 3.12 (Unicode 15.0) 에서는 미할당이지만 이후 Unicode 에서 대소문자가 생긴 문자.
/// Rust 표준 라이브러리는 더 새 Unicode 를 따르므로, 이 문자들은 기준대로 그대로 둔다.
fn is_cased_after_unicode_15(c: char) -> bool {
    matches!(
        c,
        '\u{1C89}'..='\u{1C8A}'      // Cyrillic TJE (16.0)
            | '\u{A7CB}'..='\u{A7CD}' // Latin RAMS HORN, S WITH DIAGONAL STROKE (16.0)
            | '\u{A7CE}'..='\u{A7CF}' // Latin PHARYNGEAL VOICED FRICATIVE (17.0)
            | '\u{A7D2}'              // Latin CAPITAL DOUBLE THORN (17.0)
            | '\u{A7D4}'              // Latin CAPITAL DOUBLE WYNN (17.0)
            | '\u{A7DA}'..='\u{A7DC}' // Latin LAMBDA, LAMBDA WITH STROKE (16.0)
            | '\u{10D40}'..='\u{10D8F}' // Garay 블록 (16.0)
    )
}

/// Python `str.lower()` 와 같은 소문자 변환 (계약 2절 4항).
/// 전체 매핑(İ → i̇)과 어말 시그마(Σ → ς) 규칙은 `str::to_lowercase` 가 Python 과 같게 처리한다.
pub fn to_lower(word: &str) -> String {
    if !word.chars().any(is_cased_after_unicode_15) {
        return word.to_lowercase();
    }
    // 기준에서 미할당인 문자는 바꾸지 않고, Σ 의 어말형 판단에서도
    // 대소문자와 무관한 문자('0')로 본다.
    let masked: String = word
        .chars()
        .map(|c| if is_cased_after_unicode_15(c) { '0' } else { c })
        .collect();
    let masked_lower = masked.to_lowercase();
    let mut lowered = String::with_capacity(word.len());
    for (i, c) in word.char_indices() {
        if is_cased_after_unicode_15(c) {
            lowered.push(c);
        } else if c == 'Σ' {
            // Σ 앞까지의 변환 길이는 Σ 와 무관하다 (σ, ς 모두 2바이트).
            let at = masked[..i].to_lowercase().len();
            lowered.extend(masked_lower[at..].chars().next());
        } else {
            lowered.extend(c.to_lowercase());
        }
    }
    lowered
}

/// 공백으로 자르고, 앞뒤 문장 부호를 떼고, 소문자로 바꾼다. 빈 조각은 버린다.
pub fn tokenize(text: &str) -> Vec<String> {
    text.split(is_python_whitespace)
        .map(|raw| raw.trim_matches(is_punctuation))
        .filter(|word| !word.is_empty())
        .map(to_lower)
        .collect()
}

/// 빈도 내림차순, 같은 빈도는 단어 오름차순(코드 포인트 순)으로 상위 top_n 개.
pub fn count_words(words: &[String], top_n: usize) -> Report {
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for word in words {
        *counts.entry(word.as_str()).or_insert(0) += 1;
    }
    let unique_words = counts.len();
    let mut ranked: Vec<(&str, usize)> = counts.into_iter().collect();
    // UTF-8 바이트 순서는 코드 포인트 순서와 같다.
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    ranked.truncate(top_n);
    Report {
        total_words: words.len(),
        unique_words,
        top: ranked
            .into_iter()
            .map(|(word, count)| (word.to_string(), count))
            .collect(),
    }
}

pub fn format_text(report: &Report) -> String {
    let mut out = format!(
        "words: {}\nunique: {}\n",
        report.total_words, report.unique_words
    );
    for (word, count) in &report.top {
        let _ = writeln!(out, "{count}\t{word}");
    }
    out
}

/// Python `json.dumps(..., ensure_ascii=False)` 와 같은 문자열 이스케이프.
fn push_json_string(out: &mut String, s: &str) {
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
            c if c < '\u{20}' => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn format_json(report: &Report) -> String {
    let mut out = format!(
        "{{\"words\":{},\"unique\":{},\"top\":[",
        report.total_words, report.unique_words
    );
    for (i, (word, count)) in report.top.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str("{\"word\":");
        push_json_string(&mut out, word);
        let _ = write!(out, ",\"count\":{count}}}");
    }
    out.push_str("]}\n");
    out
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Options {
    pub file: OsString,
    pub top: usize,
    pub json: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    Run(Options),
    Help,
}

/// `--top` 값: ASCII 숫자만, 1 이상. 너무 커서 usize 를 넘으면 usize::MAX 로 본다.
fn parse_top(value: &str) -> Result<usize, String> {
    if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(format!("argument --top: not an integer: {value}"));
    }
    match value.parse::<usize>() {
        Ok(0) => Err(format!("argument --top: must be at least 1: {value}")),
        Ok(number) => Ok(number),
        Err(_) => Ok(usize::MAX),
    }
}

/// 명령행 인자(프로그램 이름 제외)를 해석한다. 오류면 사용자에게 보일 한 줄 메시지를 돌려준다.
pub fn parse_args<I>(args: I) -> Result<Command, String>
where
    I: IntoIterator<Item = OsString>,
{
    let mut file: Option<OsString> = None;
    let mut top = DEFAULT_TOP;
    let mut json = false;
    let mut options_ended = false;
    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        let is_option = !options_ended && arg != "-" && arg.as_encoded_bytes().starts_with(b"-");
        if !is_option {
            if file.is_some() {
                return Err(format!("unrecognized arguments: {}", arg.to_string_lossy()));
            }
            file = Some(arg);
            continue;
        }
        match arg.to_str() {
            Some("--") => options_ended = true,
            Some("--json") => json = true,
            Some("-h" | "--help") => return Ok(Command::Help),
            Some("--top") => {
                let value = args
                    .next()
                    .ok_or_else(|| "argument --top: expected one argument".to_string())?;
                top = parse_top(&value.to_string_lossy())?;
            }
            Some(other) if other.starts_with("--top=") => {
                let (_, value) = other.split_once('=').unwrap_or_default();
                top = parse_top(value)?;
            }
            _ => {
                return Err(format!("unrecognized arguments: {}", arg.to_string_lossy()));
            }
        }
    }
    let file = file.ok_or_else(|| "the following arguments are required: FILE".to_string())?;
    Ok(Command::Run(Options { file, top, json }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words(list: &[&str]) -> Vec<String> {
        list.iter().map(|w| w.to_string()).collect()
    }

    fn parse(list: &[&str]) -> Result<Command, String> {
        parse_args(list.iter().map(OsString::from))
    }

    #[test]
    fn tokenize_strips_punctuation_and_lowercases() {
        assert_eq!(
            tokenize("\"Hello,\" Don't e-mail... RUST!"),
            words(&["hello", "don't", "e-mail", "rust"])
        );
    }

    #[test]
    fn tokenize_drops_punctuation_only_pieces() {
        assert!(tokenize("!!! --- ... “” ‘’ … ·").is_empty());
    }

    #[test]
    fn tokenize_strips_unicode_quotes_only_at_edges() {
        assert_eq!(
            tokenize("“Quoted” ‘single’ wait… ·dot· a·b"),
            words(&["quoted", "single", "wait", "dot", "a·b"])
        );
    }

    #[test]
    fn tokenize_uses_python_whitespace() {
        // U+001C..U+001F 는 Python 에서 공백, U+200B 와 U+FEFF 는 공백이 아니다.
        assert_eq!(
            tokenize("a\u{1C}b\u{1D}c\u{1E}d\u{1F}e\u{85}f\u{A0}g\u{3000}h"),
            words(&["a", "b", "c", "d", "e", "f", "g", "h"])
        );
        assert_eq!(
            tokenize("a\u{200B}b \u{FEFF}c"),
            words(&["a\u{200B}b", "\u{FEFF}c"])
        );
        assert_eq!(
            tokenize("one\r\ntwo\rthree"),
            words(&["one", "two", "three"])
        );
    }

    #[test]
    fn lower_matches_python_special_cases() {
        assert_eq!(to_lower("İ"), "i\u{307}");
        assert_eq!(to_lower("ΟΔΟΣ"), "οδος");
        assert_eq!(to_lower("Σ"), "σ");
        assert_eq!(to_lower("ΑΣ'Α"), "ασ'α");
        assert_eq!(to_lower("ẞ"), "ß");
    }

    #[test]
    fn lower_keeps_characters_newer_than_unicode_15() {
        assert_eq!(to_lower("\u{A7CB}"), "\u{A7CB}");
        assert_eq!(to_lower("\u{10D50}A"), "\u{10D50}a");
        // 새 문자는 대소문자 없는 문자로 보므로 Σ 는 어말형이 된다.
        assert_eq!(to_lower("ΑΣ\u{A7DB}"), "ας\u{A7DB}");
        assert_eq!(to_lower("\u{A7DB}Σ"), "\u{A7DB}σ");
    }

    #[test]
    fn ties_are_sorted_by_word() {
        let report = count_words(&words(&["b", "a", "c", "b", "a", "c", "d"]), 10);
        assert_eq!(
            report.top,
            [
                ("a".to_string(), 2),
                ("b".to_string(), 2),
                ("c".to_string(), 2),
                ("d".to_string(), 1)
            ]
        );
        assert_eq!(report.total_words, 7);
        assert_eq!(report.unique_words, 4);
    }

    #[test]
    fn top_limits_entries() {
        let report = count_words(&words(&["x", "y", "x"]), 1);
        assert_eq!(report.top, [("x".to_string(), 2)]);
        assert_eq!(report.unique_words, 2);
    }

    #[test]
    fn text_format() {
        let report = count_words(&words(&["rust", "is", "rust"]), 10);
        assert_eq!(
            format_text(&report),
            "words: 3\nunique: 2\n2\trust\n1\tis\n"
        );
    }

    #[test]
    fn json_format_keeps_non_ascii_and_escapes_like_python() {
        let report = count_words(&words(&["러스트", "a\"b\\c", "x\u{1}\u{8}\u{7F}"]), 10);
        assert_eq!(
            format_json(&report),
            "{\"words\":3,\"unique\":3,\"top\":[{\"word\":\"a\\\"b\\\\c\",\"count\":1},\
             {\"word\":\"x\\u0001\\b\u{7F}\",\"count\":1},{\"word\":\"러스트\",\"count\":1}]}\n"
        );
    }

    #[test]
    fn empty_json() {
        let report = count_words(&[], 10);
        assert_eq!(
            format_json(&report),
            "{\"words\":0,\"unique\":0,\"top\":[]}\n"
        );
    }

    #[test]
    fn parse_defaults_and_options() {
        assert_eq!(
            parse(&["a.txt"]),
            Ok(Command::Run(Options {
                file: "a.txt".into(),
                top: 10,
                json: false
            }))
        );
        assert_eq!(
            parse(&["--json", "--top", "3", "a.txt", "--top=05"]),
            Ok(Command::Run(Options {
                file: "a.txt".into(),
                top: 5,
                json: true
            }))
        );
        assert_eq!(
            parse(&["--", "-a.txt"]),
            Ok(Command::Run(Options {
                file: "-a.txt".into(),
                top: 10,
                json: false
            }))
        );
        assert_eq!(
            parse(&["a.txt", "--top", "99999999999999999999999"]),
            Ok(Command::Run(Options {
                file: "a.txt".into(),
                top: usize::MAX,
                json: false
            }))
        );
        assert_eq!(parse(&["--help"]), Ok(Command::Help));
    }

    #[test]
    fn parse_errors() {
        let cases: [&[&str]; 11] = [
            &[],
            &["a.txt", "--top", "0"],
            &["a.txt", "--top", "abc"],
            &["a.txt", "--top", "-1"],
            &["a.txt", "--top", "+5"],
            &["a.txt", "--top", "１"],
            &["a.txt", "--top", "1_0"],
            &["a.txt", "--top"],
            &["a.txt", "--bogus"],
            &["a.txt", "--to", "3"],
            &["a.txt", "b.txt"],
        ];
        for args in cases {
            assert!(parse(args).is_err(), "{args:?}");
        }
    }
}
