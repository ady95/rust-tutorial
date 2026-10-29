//! 정상 출력 (계약 3절): 텍스트 형식과 JSON 형식.

use crate::text::Report;
use std::fmt::Write as _;

/// `words: N\nunique: M\n<count>\t<word>\n...`
pub fn format_text(report: &Report) -> String {
    let mut out = String::new();
    let _ = writeln!(out, "words: {}", report.total_words);
    let _ = writeln!(out, "unique: {}", report.unique_words);
    for (word, count) in &report.top {
        let _ = writeln!(out, "{count}\t{word}");
    }
    out
}

/// Python `json.dumps(s, ensure_ascii=False)` 와 같은 문자열 이스케이프 (따옴표 포함)
pub fn json_string(out: &mut String, s: &str) {
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
            c if u32::from(c) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", u32::from(c));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// `{"words":N,"unique":M,"top":[{"word":"..","count":K},...]}\n`
pub fn format_json(report: &Report) -> String {
    let mut out = String::new();
    let _ = write!(
        out,
        "{{\"words\":{},\"unique\":{},\"top\":[",
        report.total_words, report.unique_words
    );
    for (i, (word, count)) in report.top.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str("{\"word\":");
        json_string(&mut out, word);
        let _ = write!(out, ",\"count\":{count}}}");
    }
    out.push_str("]}\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::text::{count_words, tokenize};

    fn json_for(text: &str) -> String {
        format_json(&count_words(&tokenize(text), 10))
    }

    #[test]
    fn r8_json_escapes() {
        // 기대값: verify/probe_text.py 의 Python json.dumps 결과
        assert_eq!(
            json_for("a\u{0}b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\\u0000b\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\u{8}b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\\bb\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\u{7f}b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\u{7f}b\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\"b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\\\"b\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\\b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\\\\b\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\u{200e}b"),
            "{\"words\":1,\"unique\":1,\"top\":[{\"word\":\"a\u{200e}b\",\"count\":1}]}\n"
        );
        assert_eq!(
            json_for("a\u{1b}b a\u{c}b"),
            "{\"words\":3,\"unique\":3,\"top\":[{\"word\":\"a\",\"count\":1},\
             {\"word\":\"a\\u001bb\",\"count\":1},{\"word\":\"b\",\"count\":1}]}\n"
        );
        assert_eq!(json_for(""), "{\"words\":0,\"unique\":0,\"top\":[]}\n");
        assert_eq!(
            json_for("러스트 러스트 rust"),
            "{\"words\":3,\"unique\":2,\"top\":[{\"word\":\"러스트\",\"count\":2},{\"word\":\"rust\",\"count\":1}]}\n"
        );
    }

    #[test]
    fn text_format() {
        let report = count_words(&tokenize("b a b"), 10);
        assert_eq!(format_text(&report), "words: 3\nunique: 2\n2\tb\n1\ta\n");
        let empty = count_words(&[], 10);
        assert_eq!(format_text(&empty), "words: 0\nunique: 0\n");
    }
}
