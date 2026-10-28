//! wordstats — 단어 통계. python_src/wordstats.py 와 같은 출력을 낸다.

use std::collections::HashMap;

pub fn normalize(word: &str) -> String {
    let lower = word.to_lowercase();
    lower.trim_matches(|c: char| c.is_ascii_punctuation()).to_string()
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
    if let Some(n) = counts.get(source).copied() {
        *counts.entry(target.to_string()).or_insert(0) += n;
        counts.insert(source.to_string(), 0);
    }
}

pub fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {
    if b.chars().count() > a.chars().count() { b } else { a }
}

pub fn longest(words: &[String]) -> Option<&str> {
    if words.len() == 0 {
        return None;
    }
    let mut best: &str = &words[0];
    for i in 1..words.len() {
        best = longer(best, &words[i]);
    }
    Some(best)
}

pub fn top_n(counts: &HashMap<String, usize>, n: usize) -> Vec<(String, usize)> {
    let mut items: Vec<(String, usize)> = counts.iter().map(|(w, c)| (w.clone(), *c)).collect();
    items.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| b.0.cmp(&a.0)));
    items.truncate(n);
    return items;
}

pub fn summary(text: &str, top: usize, min: usize) -> String {
    let words = tokenize(text);
    let mut counts = count(&words);
    drop_rare(&mut counts, min);
    let header = format!(
        "words: {}\nunique: {}\nlongest: {}",
        words.len(),
        counts.len(),
        longest(&words).unwrap_or("-")
    );
    let mut lines: Vec<String> = vec![header];
    for (w, n) in top_n(&counts, top) {
        lines.push(format!("{n}\t{w}"));
    }
    lines.join("\n")
}
