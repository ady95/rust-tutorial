//! 출력: 기본 목록과 `json.dumps(..., ensure_ascii=False)` 형식의 JSON.

use crate::slug::Entry;

pub fn render(entries: &[Entry], min_level: u8) -> String {
    let mut out = String::new();
    for e in entries {
        for _ in 0..usize::from(e.level.saturating_sub(min_level)) {
            out.push_str("  ");
        }
        out.push_str("- [");
        out.push_str(e.text);
        out.push_str("](#");
        out.push_str(&e.slug);
        out.push_str(")\n");
    }
    out
}

/// 번호 목록: 깊이마다 1부터 세고, 얕은 제목이 나오면 더 깊은 번호를 되돌린다. 들여쓰기는 깊이당 3칸.
pub fn render_numbered(entries: &[Entry], min_level: u8) -> String {
    let mut counters = [0usize; 7];
    let mut out = String::new();
    for e in entries {
        let depth = usize::from(e.level.saturating_sub(min_level));
        counters[depth] += 1;
        for c in &mut counters[depth + 1..] {
            *c = 0;
        }
        out.push_str(&"   ".repeat(depth));
        out.push_str(&format!("{}. [{}](#{})\n", counters[depth], e.text, e.slug));
    }
    out
}

/// JSON 문자열 이스케이프: `"` `\` `\b` `\f` `\n` `\r` `\t` 와 나머지 0x00~0x1f 의 `\u00xx`.
fn json_escape(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn render_json(entries: &[Entry]) -> String {
    let mut out = String::from("[");
    for (i, e) in entries.iter().enumerate() {
        if i > 0 {
            out.push_str(", ");
        }
        out.push_str("{\"level\": ");
        out.push_str(&e.level.to_string());
        out.push_str(", \"text\": ");
        json_escape(e.text, &mut out);
        out.push_str(", \"slug\": ");
        json_escape(&e.slug, &mut out);
        out.push('}');
    }
    out.push_str("]\n");
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entry(level: u8, text: &str) -> Entry<'_> {
        Entry {
            level,
            text,
            slug: "s".to_string(),
        }
    }

    #[test]
    fn indentation() {
        assert_eq!(render(&[entry(6, "t")], 6), "- [t](#s)\n");
        assert_eq!(
            render(&[entry(6, "t")], 1),
            format!("{}- [t](#s)\n", " ".repeat(10))
        );
    }

    #[test]
    fn numbered() {
        let es = [
            entry(1, "A"),
            entry(2, "B"),
            entry(2, "C"),
            entry(1, "D"),
            entry(3, "E"),
            entry(2, "F"),
        ];
        assert_eq!(
            render_numbered(&es, 1),
            "1. [A](#s)\n   1. [B](#s)\n   2. [C](#s)\n2. [D](#s)\n      1. [E](#s)\n   1. [F](#s)\n"
        );
    }

    #[test]
    fn json_format() {
        assert_eq!(render_json(&[]), "[]\n");
        let got = render_json(&[entry(1, "a\"\\\x01\x08\x1f\t\x7f/é")]);
        assert_eq!(
            got,
            "[{\"level\": 1, \"text\": \"a\\\"\\\\\\u0001\\b\\u001f\\t\x7f/é\", \"slug\": \"s\"}]\n"
        );
    }
}
