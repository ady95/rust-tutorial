use crate::text::Report;

pub fn format_text(report: &Report) -> String {
    let mut out = format!(
        "words: {}\nunique: {}\n",
        report.total_words, report.unique_words
    );
    for (word, count) in &report.top {
        out.push_str(&format!("{count}\t{word}\n"));
    }
    out
}

/// Python json.dumps(ensure_ascii=False) 의 문자열 이스케이프
fn push_json_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{C}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
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
        out.push_str(&format!(",\"count\":{count}}}"));
    }
    out.push_str("]}\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn report(words: &[&str]) -> Report {
        Report {
            total_words: words.len(),
            unique_words: words.len(),
            top: words.iter().map(|w| (w.to_string(), 1)).collect(),
        }
    }

    #[test]
    fn json_escapes_like_python() {
        let json = format_json(&report(&[
            "a\0b", "a\x08b", "a\x7fb", "a\"b", "a\\b", "한글",
        ]));
        assert_eq!(
            json,
            "{\"words\":6,\"unique\":6,\"top\":[{\"word\":\"a\\u0000b\",\"count\":1},{\"word\":\"a\\bb\",\"count\":1},{\"word\":\"a\x7fb\",\"count\":1},{\"word\":\"a\\\"b\",\"count\":1},{\"word\":\"a\\\\b\",\"count\":1},{\"word\":\"한글\",\"count\":1}]}\n"
        );
    }

    #[test]
    fn empty_top_is_empty_array() {
        assert_eq!(
            format_json(&report(&[])),
            "{\"words\":0,\"unique\":0,\"top\":[]}\n"
        );
        assert_eq!(format_text(&report(&[])), "words: 0\nunique: 0\n");
    }
}
