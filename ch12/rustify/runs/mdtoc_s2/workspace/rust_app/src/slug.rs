//! 앵커(slug) 만들기와 목차 항목 만들기.

use std::collections::{HashMap, HashSet};

use crate::headings::headings;
use crate::pystr;

pub struct Entry<'a> {
    pub level: u8,
    pub text: &'a str,
    pub slug: String,
}

/// 소문자로 바꾸고, 글자·숫자·_·-·공백만 남기고, 공백을 -로 바꾼다.
/// 겹치면 -1, -2, … 를 붙이되, 이미 쓴 앵커와 겹치지 않을 때까지 번호를 올린다.
pub fn slugify(
    title: &str,
    counts: &mut HashMap<String, usize>,
    used: &mut HashSet<String>,
) -> String {
    let base: String = pystr::lower(title)
        .chars()
        .filter(|&c| pystr::is_word_char(c) || c == '-' || c == ' ')
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

/// 걸러 낼 제목도 앵커 번호에는 들어간다.
pub fn build(text: &str, min_level: u8, max_level: u8) -> Vec<Entry<'_>> {
    let mut counts = HashMap::new();
    let mut used = HashSet::new();
    let mut entries = Vec::new();
    for (level, title) in headings(text) {
        let slug = slugify(title, &mut counts, &mut used);
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
        let mut counts = HashMap::new();
        let mut used = HashSet::new();
        titles
            .iter()
            .map(|t| slugify(t, &mut counts, &mut used))
            .collect()
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
    fn anchors_never_collide() {
        assert_eq!(slugs(&["A", "a", "a-1", "a"]), ["a", "a-1", "a-1-1", "a-2"]);
        assert_eq!(slugs(&["!!!", "!!"]), ["", "-1"]);
    }

    #[test]
    fn filtered_headings_still_count() {
        let entries = build("# a\n## a\n## a\n", 2, 6);
        let got: Vec<&str> = entries.iter().map(|e| e.slug.as_str()).collect();
        assert_eq!(got, ["a-1", "a-2"]);
    }
}
