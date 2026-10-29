//! 정상 출력 형식(계약 3절). 기준 구현의 format_text, format_json 에 해당한다.

use std::fmt::Write;

use crate::text::Report;

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

/// json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n" 과 같다. 키 순서는 고정이다.
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
        push_json_str(&mut out, word);
        let _ = write!(out, ",\"count\":{count}}}");
    }
    out.push_str("]}\n");
    out
}

/// Python json 의 ensure_ascii=False 이스케이프: " \ 와 \b \f \n \r \t 는 짧은 형식,
/// 그 밖의 U+0000–U+001F 는 \u00xx(소문자 16진). U+007F 와 ASCII 밖의 글자는 그대로 쓴다.
fn push_json_str(out: &mut String, s: &str) {
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
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            _ => out.push(c),
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;

    fn report(top: &[(&str, usize)]) -> Report {
        Report {
            total_words: 5,
            unique_words: 3,
            top: top.iter().map(|&(w, c)| (w.to_string(), c)).collect(),
        }
    }

    #[test]
    fn text_format() {
        assert_eq!(
            format_text(&report(&[("rust", 2), ("러스트", 1)])),
            "words: 5\nunique: 3\n2\trust\n1\t러스트\n"
        );
    }

    #[test]
    fn json_format_and_escapes() {
        assert_eq!(
            format_json(&report(&[("rust", 2)])),
            "{\"words\":5,\"unique\":3,\"top\":[{\"word\":\"rust\",\"count\":2}]}\n"
        );
        assert_eq!(
            format_json(&report(&[])),
            "{\"words\":5,\"unique\":3,\"top\":[]}\n"
        );
        let mut s = String::new();
        push_json_str(
            &mut s,
            "a\"b\\c\u{8}\u{c}\n\r\t\0\u{1b}\u{1f}\u{7f}\u{2028}한",
        );
        assert_eq!(
            s,
            "\"a\\\"b\\\\c\\b\\f\\n\\r\\t\\u0000\\u001b\\u001f\u{7f}\u{2028}한\""
        );
    }
}
