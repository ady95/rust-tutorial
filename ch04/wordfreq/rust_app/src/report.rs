//! 단어 규칙(계약 2절)과 정상 출력 형식(계약 3절).

use std::collections::HashMap;
use std::fmt::Write;

use crate::pystr;

/// 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
const PUNCTUATION: &str = concat!("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~", "“”‘’…·");

#[derive(Debug, PartialEq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, usize)>,
}

/// 공백(Python str.split 기준)으로 자르고, 앞뒤 문장 부호를 떼고, 소문자로 바꾼다.
pub fn tokenize(text: &str) -> Vec<String> {
    text.split(pystr::is_space)
        .map(|raw| raw.trim_matches(|c| PUNCTUATION.contains(c)))
        .filter(|word| !word.is_empty())
        .map(pystr::lower)
        .collect()
}

/// 빈도 내림차순, 같은 빈도는 단어 오름차순(코드 포인트 순)으로 상위 top_n 개.
/// String 의 바이트(UTF-8) 순서는 코드 포인트 순서와 같다.
pub fn count_words(words: Vec<String>, top_n: usize) -> Report {
    let total_words = words.len();
    let mut counter: HashMap<String, usize> = HashMap::new();
    for word in words {
        *counter.entry(word).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(String, usize)> = counter.into_iter().collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    ranked.truncate(top_n);
    Report { total_words, unique_words, top: ranked }
}

pub fn format_text(report: &Report) -> String {
    let mut out = format!("words: {}\nunique: {}\n", report.total_words, report.unique_words);
    for (word, count) in &report.top {
        writeln!(out, "{count}\t{word}").unwrap();
    }
    out
}

pub fn format_json(report: &Report) -> String {
    let top: Vec<String> = report
        .top
        .iter()
        .map(|(word, count)| format!("{{\"word\":{},\"count\":{count}}}", json_string(word)))
        .collect();
    format!(
        "{{\"words\":{},\"unique\":{},\"top\":[{}]}}\n",
        report.total_words,
        report.unique_words,
        top.join(",")
    )
}

/// Python `json.dumps(s, ensure_ascii=False)` 와 같은 문자열 표기.
fn json_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if c < '\u{20}' => write!(out, "\\u{:04x}", c as u32).unwrap(),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(words: &[&str]) -> Vec<String> {
        words.iter().map(|w| w.to_string()).collect()
    }

    #[test]
    fn tokenize_strips_punctuation_and_lowercases() {
        assert_eq!(tokenize("\"Hello,\" Don't e-mail... RUST!"), ["hello", "don't", "e-mail", "rust"]);
    }

    #[test]
    fn tokenize_drops_punctuation_only_pieces() {
        assert!(tokenize("!!! --- ...").is_empty());
    }

    #[test]
    fn tokenize_strips_unicode_punctuation() {
        assert_eq!(tokenize("“Quoted” ‘single’ wait… ·dot·"), ["quoted", "single", "wait", "dot"]);
    }

    #[test]
    fn ties_are_sorted_by_word() {
        let report = count_words(strings(&["b", "a", "c", "b", "a", "c", "d"]), 10);
        let expected = [("a", 2), ("b", 2), ("c", 2), ("d", 1)].map(|(w, c)| (w.to_string(), c));
        assert_eq!(report.top, expected);
    }

    #[test]
    fn text_output() {
        let report = count_words(strings(&["rust", "is", "rust"]), 1);
        assert_eq!(format_text(&report), "words: 3\nunique: 2\n2\trust\n");
    }

    #[test]
    fn json_output_keeps_korean_and_escapes_controls() {
        let report = count_words(strings(&["러스트", "a\"b\\", "x\u{1}\u{8}\u{7f}"]), 10);
        assert_eq!(
            format_json(&report),
            "{\"words\":3,\"unique\":3,\"top\":[{\"word\":\"a\\\"b\\\\\",\"count\":1},\
             {\"word\":\"x\\u0001\\b\u{7f}\",\"count\":1},{\"word\":\"러스트\",\"count\":1}]}\n"
        );
    }

    #[test]
    fn empty_json() {
        assert_eq!(format_json(&count_words(Vec::new(), 10)), "{\"words\":0,\"unique\":0,\"top\":[]}\n");
    }
}
