//! 정상 출력 형식(계약 3절).

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

/// Python json.dumps(ensure_ascii=False) 와 같은 문자열 이스케이프
fn push_json_string(out: &mut String, s: &str) {
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
            c if (c as u32) < 0x20 => {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn report(top: &[(&str, usize)]) -> Report {
        Report {
            total_words: 5,
            unique_words: 3,
            top: top.iter().map(|(w, c)| (w.to_string(), *c)).collect(),
        }
    }

    #[test]
    fn text_format() {
        let r = report(&[("rust", 2), ("한글", 1)]);
        assert_eq!(format_text(&r), "words: 5\nunique: 3\n2\trust\n1\t한글\n");
        assert_eq!(format_text(&report(&[])), "words: 5\nunique: 3\n");
    }

    #[test]
    fn json_format() {
        let r = report(&[("rust", 2), ("한글", 1)]);
        assert_eq!(
            format_json(&r),
            "{\"words\":5,\"unique\":3,\"top\":[{\"word\":\"rust\",\"count\":2},{\"word\":\"한글\",\"count\":1}]}\n"
        );
        assert_eq!(
            format_json(&report(&[])),
            "{\"words\":5,\"unique\":3,\"top\":[]}\n"
        );
    }

    #[test]
    fn json_escapes_like_python() {
        // 기대값은 json.dumps(..., ensure_ascii=False) 결과
        let r = report(&[("a\0b\u{8}\u{c}\u{1f}\"\\\u{7f}\u{2028}", 1)]);
        assert_eq!(
            format_json(&r),
            "{\"words\":5,\"unique\":3,\"top\":[{\"word\":\"a\\u0000b\\b\\f\\u001f\\\"\\\\\u{7f}\u{2028}\",\"count\":1}]}\n"
        );
    }
}
