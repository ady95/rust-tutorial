//! wordfreq: 텍스트의 단어 빈도를 센다. `python_src/wordfreq.py`의 Rust 이식이다.
//!
//! 동작 계약은 `contracts/behavior_spec.md`에 있다. 이 모듈은 파일·표준 입출력에 접근하지 않는다.

use std::collections::HashMap;
use std::ffi::OsString;
use std::fmt::Write as _;

/// 기본 상위 단어 수 (계약 1절).
pub const DEFAULT_TOP: usize = 10;

/// 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
pub const PUNCTUATION: &str = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~“”‘’…·";

pub const USAGE: &str = "usage: wordfreq FILE [--top N] [--json]";

/// Python 3.12(Unicode 15.0)에는 없고 Rust 표준 라이브러리(Unicode 17.0)에서 대소문자가 있는 문자.
/// Python은 이 문자를 미할당 문자로 보므로 소문자로 바꾸지 않고, 그리스 대문자 시그마의
/// 어말 판정에서도 cased·case-ignorable이 아닌 문자로 취급한다.
const UNKNOWN_TO_PYTHON: &[(char, char)] = &[
    ('\u{1C89}', '\u{1C8A}'),   // 16.0 키릴 TJE
    ('\u{A7CB}', '\u{A7CF}'),   // 16.0 A7CB~A7CD, 17.0 A7CE~A7CF
    ('\u{A7D2}', '\u{A7D2}'),   // 17.0
    ('\u{A7D4}', '\u{A7D4}'),   // 17.0
    ('\u{A7DA}', '\u{A7DC}'),   // 16.0
    ('\u{A7F1}', '\u{A7F1}'),   // 17.0
    ('\u{10D50}', '\u{10D65}'), // 16.0 Garay 대문자
    ('\u{10D70}', '\u{10D85}'), // 16.0 Garay 소문자
    ('\u{16EA0}', '\u{16EB8}'), // 17.0 Beria Erfe 대문자
    ('\u{16EBB}', '\u{16ED3}'), // 17.0 Beria Erfe 소문자
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, usize)>,
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

/// Python `str.split()`(인자 없음)이 공백으로 보는 문자 (Unicode 15.0 기준).
pub fn is_python_whitespace(c: char) -> bool {
    matches!(
        c,
        '\t'..='\r'
            | '\u{1c}'..='\u{20}'
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

pub fn is_punctuation(c: char) -> bool {
    PUNCTUATION.contains(c)
}

fn is_unknown_to_python(c: char) -> bool {
    UNKNOWN_TO_PYTHON
        .iter()
        .any(|&(first, last)| (first..=last).contains(&c))
}

/// Python `str.lower()`와 같은 규칙으로 소문자로 바꾼다.
///
/// Rust `str::to_lowercase`도 SpecialCasing과 어말 시그마 규칙을 따르므로, Python이 모르는 문자에서
/// 문자열을 끊어 각 조각만 변환한다. 끊긴 자리는 시그마 판정에서 문자열 끝과 같은 효과를 낸다.
pub fn to_lower(word: &str) -> String {
    let mut lowered = String::with_capacity(word.len());
    let mut rest = word;
    while let Some(pos) = rest.find(is_unknown_to_python) {
        lowered.push_str(&rest[..pos].to_lowercase());
        let unknown = rest[pos..]
            .chars()
            .next()
            .expect("find returned a char boundary");
        lowered.push(unknown);
        rest = &rest[pos + unknown.len_utf8()..];
    }
    lowered.push_str(&rest.to_lowercase());
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
    let mut counter: HashMap<&str, usize> = HashMap::new();
    for word in words {
        *counter.entry(word.as_str()).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(&str, usize)> = counter.into_iter().collect();
    // UTF-8 바이트 순서는 코드 포인트 순서와 같다.
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    ranked.truncate(top_n);
    Report {
        total_words: words.len(),
        unique_words,
        top: ranked
            .into_iter()
            .map(|(word, count)| (word.to_owned(), count))
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

/// `json.dumps(data, ensure_ascii=False, separators=(",", ":"))`와 같은 한 줄 JSON.
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

/// Python json 모듈(ensure_ascii=False)의 문자열 이스케이프: `"`, `\`, U+0000~U+001F만 바꾼다.
fn push_json_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\0'..='\u{1f}' => {
                let _ = write!(out, "\\u{:04x}", u32::from(c));
            }
            _ => out.push(c),
        }
    }
    out.push('"');
}

/// `--top` 값. ASCII 숫자만 받고 1 이상이어야 한다. 너무 큰 값은 "전부"와 같으므로 포화시킨다.
pub fn parse_top(value: &str) -> Result<usize, String> {
    if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(format!("argument --top: not an integer: {value}"));
    }
    let number = value.bytes().fold(0usize, |acc, b| {
        acc.saturating_mul(10).saturating_add(usize::from(b - b'0'))
    });
    if number < 1 {
        return Err(format!("argument --top: must be at least 1: {value}"));
    }
    Ok(number)
}

/// 명령행 인자(프로그램 이름 제외)를 해석한다. 실패하면 오류 한 줄을 돌려준다.
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
        if !options_ended {
            let text = arg.to_string_lossy();
            match text.as_ref() {
                "--" => {
                    options_ended = true;
                    continue;
                }
                "-h" | "--help" => return Ok(Command::Help),
                "--json" => {
                    json = true;
                    continue;
                }
                "--top" => {
                    let value = args.next().ok_or("argument --top: expected one argument")?;
                    top = parse_top(&value.to_string_lossy())?;
                    continue;
                }
                _ => {}
            }
            if let Some(value) = text.strip_prefix("--top=") {
                top = parse_top(value)?;
                continue;
            }
            if text.len() > 1 && text.starts_with('-') {
                return Err(format!("unrecognized argument: {text}"));
            }
        }
        if file.is_some() {
            return Err(format!("unrecognized argument: {}", arg.to_string_lossy()));
        }
        file = Some(arg);
    }

    let file = file.ok_or("the following arguments are required: FILE")?;
    Ok(Command::Run(Options { file, top, json }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    fn args(items: &[&str]) -> Result<Command, String> {
        parse_args(items.iter().map(OsString::from))
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
        assert!(tokenize("!!! --- ...").is_empty());
    }

    #[test]
    fn tokenize_strips_typographic_punctuation() {
        assert_eq!(
            tokenize("“Quoted” ‘single’ wait… ·dot·"),
            words(&["quoted", "single", "wait", "dot"])
        );
    }

    #[test]
    fn whitespace_matches_python_split() {
        // Python은 U+001C~U+001F도 공백으로 보지만 Rust char::is_whitespace는 아니다.
        assert_eq!(tokenize("a\u{1c}b\u{1f}c"), words(&["a", "b", "c"]));
        assert_eq!(
            tokenize("a\u{a0}b\u{3000}c\u{2029}d\r\ne"),
            words(&["a", "b", "c", "d", "e"])
        );
        // 폭 없는 공백(U+200B)과 BOM은 Python에서도 공백이 아니다.
        assert_eq!(
            tokenize("a\u{200b}b \u{feff}c"),
            words(&["a\u{200b}b", "\u{feff}c"])
        );
    }

    #[test]
    fn unknown_to_python_table_targets_this_unicode_version() {
        // 표는 Rust 표준 라이브러리 Unicode 17.0과 Python 3.12(15.0)의 차이로 만들었다.
        // 툴체인이 바뀌어 이 단언이 깨지면 UNKNOWN_TO_PYTHON을 다시 점검해야 한다.
        assert_eq!(char::UNICODE_VERSION, (17, 0, 0));
    }

    #[test]
    fn unknown_to_python_entries_are_cased_in_rust() {
        for &(first, last) in UNKNOWN_TO_PYTHON {
            assert!(first <= last);
            for c in first..=last {
                assert!(
                    c.is_uppercase() || c.is_lowercase(),
                    "U+{:04X}",
                    u32::from(c)
                );
            }
        }
    }

    #[test]
    fn lower_keeps_chars_unknown_to_python() {
        // Unicode 16.0·17.0에 생긴 대문자는 Python 3.12에서 그대로 남는다.
        assert_eq!(
            to_lower("\u{A7CB}\u{1C89}\u{10D50}"),
            "\u{A7CB}\u{1C89}\u{10D50}"
        );
        assert_eq!(to_lower("A\u{A7D2}B\u{16EA0}"), "a\u{A7D2}b\u{16EA0}");
        // 바로 옆의 15.0 이전 문자는 평소대로 바뀐다.
        assert_eq!(
            to_lower("\u{A7C9}\u{A7D6}\u{A7F5}"),
            "\u{A7CA}\u{A7D7}\u{A7F6}"
        );
    }

    #[test]
    fn final_sigma_treats_unknown_chars_as_uncased() {
        // Python은 미할당 문자를 cased도 case-ignorable도 아닌 문자로 본다.
        assert_eq!(to_lower("Α\u{10D70}Σ"), "α\u{10D70}σ");
        assert_eq!(to_lower("ΑΣ\u{10D70}"), "ας\u{10D70}");
    }

    #[test]
    fn lower_follows_python_rules() {
        assert_eq!(to_lower("İSTANBUL"), "i\u{307}stanbul");
        assert_eq!(to_lower("ΟΔΟΣ"), "οδος");
        assert_eq!(to_lower("ΣΑΣ."), "σας.");
        assert_eq!(to_lower("Σ"), "σ");
        assert_eq!(to_lower("ẞ"), "ß");
    }

    #[test]
    fn ties_are_sorted_by_word() {
        let report = count_words(&words(&["b", "a", "c", "b", "a", "c", "d"]), 10);
        assert_eq!(
            report.top,
            vec![
                ("a".to_string(), 2),
                ("b".to_string(), 2),
                ("c".to_string(), 2),
                ("d".to_string(), 1)
            ]
        );
    }

    #[test]
    fn ties_use_code_point_order() {
        let report = count_words(&words(&["가", "z", "é", "Z"]), 10);
        let order: Vec<&str> = report.top.iter().map(|(w, _)| w.as_str()).collect();
        assert_eq!(order, ["Z", "z", "é", "가"]);
    }

    #[test]
    fn text_output() {
        let report = count_words(&tokenize("Rust is fast. rust, RUST! is"), 2);
        assert_eq!(
            format_text(&report),
            "words: 6\nunique: 3\n3\trust\n2\tis\n"
        );
    }

    #[test]
    fn json_output_keeps_korean_and_escapes_controls() {
        let report = count_words(&words(&["러스트는", "러스트는", "a\"b\\c\u{1}\u{8}"]), 10);
        assert_eq!(
            format_json(&report),
            "{\"words\":3,\"unique\":2,\"top\":[{\"word\":\"러스트는\",\"count\":2},\
             {\"word\":\"a\\\"b\\\\c\\u0001\\b\",\"count\":1}]}\n"
        );
    }

    #[test]
    fn empty_input() {
        let report = count_words(&tokenize(""), 10);
        assert_eq!(format_text(&report), "words: 0\nunique: 0\n");
        assert_eq!(
            format_json(&report),
            "{\"words\":0,\"unique\":0,\"top\":[]}\n"
        );
    }

    #[test]
    fn parse_defaults_and_options() {
        assert_eq!(
            args(&["a.txt"]),
            Ok(Command::Run(Options {
                file: "a.txt".into(),
                top: 10,
                json: false
            }))
        );
        assert_eq!(
            args(&["--json", "--top", "3", "a.txt", "--top=05"]),
            Ok(Command::Run(Options {
                file: "a.txt".into(),
                top: 5,
                json: true
            }))
        );
        assert_eq!(
            args(&["--", "-a.txt"]),
            Ok(Command::Run(Options {
                file: "-a.txt".into(),
                top: 10,
                json: false
            }))
        );
        assert_eq!(args(&["-h"]), Ok(Command::Help));
    }

    #[test]
    fn parse_large_top_saturates() {
        assert_eq!(parse_top("99999999999999999999999"), Ok(usize::MAX));
    }

    #[test]
    fn parse_usage_errors() {
        for bad in [
            &[][..],
            &["a.txt", "--top", "0"],
            &["a.txt", "--top", "abc"],
            &["a.txt", "--top", "-1"],
            &["a.txt", "--top", "+1"],
            &["a.txt", "--top", "１"],
            &["a.txt", "--top"],
            &["a.txt", "--bogus"],
            &["a.txt", "--to", "3"],
            &["a.txt", "b.txt"],
        ] {
            assert!(args(bad).is_err(), "{bad:?}");
        }
    }
}
