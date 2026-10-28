//! wordstats — 단어 통계. python_src/wordstats.py 와 같은 출력을 낸다.

use std::collections::HashMap;

pub fn normalize(word: &str) -> &str {
    let lower = word.to_lowercase();
    lower.trim_matches(|c: char| c.is_ascii_punctuation())
}

pub fn tokenize(text: &str) -> Vec<String> {
    text.split_whitespace()
        .map(normalize)
        .filter(|w| !w.is_empty())
        .map(str::to_string)
        .collect()
}

pub fn count(words: Vec<String>) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for w in words {
        *counts.entry(w).or_insert(0) += 1;
    }
    counts
}

pub fn drop_rare(counts: &mut HashMap<String, usize>, min: usize) {
    for (word, n) in counts.iter() {
        if *n < min {
            counts.remove(word);
        }
    }
}

/// source 의 횟수를 target 에 더하고 source 는 지운다. 같은 단어면 그대로 둔다.
pub fn merge(counts: &mut HashMap<String, usize>, source: &str, target: &str) {
    if let Some(src) = counts.get_mut(source) {
        let dst = counts.entry(target.to_string()).or_insert(0);
        *dst += *src;
        *src = 0;
    }
}

pub fn longer(a: &str, b: &str) -> &str {
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
    let mut counts = count(words);
    drop_rare(&mut counts, min);
    let header = format!(
        "words: {}\nunique: {}\nlongest: {}",
        words.len(),
        counts.len(),
        longest(&words).unwrap_or("-")
    );
    let mut lines: Vec<&str> = vec![header.as_str()];
    for (w, n) in top_n(&counts, top) {
        let line = format!("{n}\t{w}");
        lines.push(line.as_str());
    }
    lines.join("\n")
}
