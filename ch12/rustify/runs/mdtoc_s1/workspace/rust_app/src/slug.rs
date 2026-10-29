//! 앵커(slug) 만들기와 목차 항목 만들기.

use std::collections::HashMap;

use crate::headings::headings;
use crate::pystr;

pub struct Entry<'a> {
    pub level: u8,
    pub text: &'a str,
    pub slug: String,
}

/// 소문자로 바꾸고, 글자·숫자·_·-·공백만 남기고, 공백을 -로 바꾼다. 겹치면 -1, -2, …
pub fn slugify(title: &str, seen: &mut HashMap<String, usize>) -> String {
    let base: String = pystr::lower(title)
        .chars()
        .filter(|&c| pystr::is_word_char(c) || c == '-' || c == ' ')
        .map(|c| if c == ' ' { '-' } else { c })
        .collect();
    let count = seen.entry(base.clone()).or_insert(0);
    let n = *count;
    *count += 1;
    if n > 0 {
        format!("{base}-{n}")
    } else {
        base
    }
}

/// 걸러 낼 제목도 앵커 번호에는 들어간다.
pub fn build(text: &str, min_level: u8, max_level: u8) -> Vec<Entry<'_>> {
    let mut seen = HashMap::new();
    let mut entries = Vec::new();
    for (level, title) in headings(text) {
        let slug = slugify(title, &mut seen);
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

#[cfg(test)]
mod tests {
    use super::*;

    fn slugs(titles: &[&str]) -> Vec<String> {
        let mut seen = HashMap::new();
        titles.iter().map(|t| slugify(t, &mut seen)).collect()
    }

    #[test]
    fn slugify_rules() {
        assert_eq!(slugs(&["İstanbul"]), ["istanbul"]);
        assert_eq!(
            slugs(&["Hello, World!", "x y\u{a0}z"]),
            ["hello-world", "x-yz"]
        );
        assert_eq!(slugs(&["ΣΊΣΥΦΟΣ"]), ["σίσυφος"]);
    }

    #[test]
    fn duplicates_keep_reference_behavior() {
        assert_eq!(slugs(&["A", "a", "a-1"]), ["a", "a-1", "a-1"]);
        assert_eq!(slugs(&["!!!", "!!"]), ["", "-1"]);
    }

    #[test]
    fn filtered_headings_still_count() {
        let entries = build("# a\n## a\n## a\n", 2, 6);
        let got: Vec<&str> = entries.iter().map(|e| e.slug.as_str()).collect();
        assert_eq!(got, ["a-1", "a-2"]);
    }
}
