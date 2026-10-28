//! wordstats — 단어 통계. python_src/wordstats.py 와 같은 출력을 낸다.

use std::collections::HashMap;

pub fn normalize(word: &str) -> String {
    word.to_lowercase()
        .trim_matches(|c: char| c.is_ascii_punctuation())
        .to_string()
}

pub fn tokenize(text: &str) -> Vec<String> {
    text.split_whitespace()
        .map(normalize)
        .filter(|w| !w.is_empty())
        .collect()
}

pub fn count(words: &[String]) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for w in words {
        *counts.entry(w.clone()).or_insert(0) += 1;
    }
    counts
}

pub fn drop_rare(counts: &mut HashMap<String, usize>, min: usize) {
    counts.retain(|_, n| *n >= min);
}

/// source 의 횟수를 target 에 더하고 source 는 지운다. 같은 단어면 그대로 둔다.
pub fn merge(counts: &mut HashMap<String, usize>, source: &str, target: &str) {
    if source == target {
        return;
    }
    if let Some(src) = counts.remove(source) {
        *counts.entry(target.to_string()).or_insert(0) += src;
    }
}

pub fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {
    if b.chars().count() > a.chars().count() {
        b
    } else {
        a
    }
}

pub fn longest(words: &[String]) -> Option<&str> {
    let mut best: Option<&str> = None;
    for w in words {
        best = Some(match best {
            None => w,
            Some(b) => longer(b, w),
        });
    }
    best
}

pub fn top_n(counts: &HashMap<String, usize>, n: usize) -> Vec<(String, usize)> {
    let mut items: Vec<(String, usize)> = counts.iter().map(|(w, c)| (w.clone(), *c)).collect();
    items.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    items.truncate(n);
    items
}

pub fn summary(text: &str, top: usize, min: usize) -> String {
    let words = tokenize(text);
    let mut counts = count(&words);
    drop_rare(&mut counts, min);
    let mut lines = vec![
        format!("words: {}", words.len()),
        format!("unique: {}", counts.len()),
        format!("longest: {}", longest(&words).unwrap_or("-")),
    ];
    for (w, n) in top_n(&counts, top) {
        lines.push(format!("{n}\t{w}"));
    }
    lines.join("\n")
}
