//! wordstats — 단어 통계. python_src/wordstats.py 와 같은 출력을 낸다.

use std::borrow::Cow;
use std::collections::HashMap;

fn is_punct(c: char) -> bool {
    c.is_ascii_punctuation()
}

/// 소문자로 바꾸고 양 끝의 ASCII 문장부호를 뗀다. 바꿀 것이 없으면 입력을 빌려 쓴다.
/// 글자마다 소문자 변환이 그대로인지 봐야 한다. 대문자 검사만으로는 U+01C5 같은 글자를 놓친다.
pub fn normalize(word: &str) -> Cow<'_, str> {
    if word.chars().any(|c| c.to_lowercase().ne([c])) {
        Cow::Owned(word.to_lowercase().trim_matches(is_punct).to_string())
    } else {
        Cow::Borrowed(word.trim_matches(is_punct))
    }
}

/// Python `str.split()` 의 공백. `char::is_whitespace` 에 없는 U+001C..U+001F 도 포함한다.
/// (처음 정답에는 없었고, 06장 runC 에이전트가 찾아 넣은 것을 반영함)
fn is_python_whitespace(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

pub fn tokenize(text: &str) -> Vec<Cow<'_, str>> {
    text.split(is_python_whitespace)
        .map(normalize)
        .filter(|w| !w.is_empty())
        .collect()
}

pub fn count<S: AsRef<str>>(words: &[S]) -> HashMap<String, usize> {
    let mut counts = HashMap::new();
    for w in words {
        let w = w.as_ref();
        if let Some(n) = counts.get_mut(w) {
            *n += 1;
        } else {
            counts.insert(w.to_string(), 1);
        }
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
    if let Some(n) = counts.remove(source) {
        *counts.entry(target.to_string()).or_insert(0) += n;
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
    longest_of(words)
}

/// `longest` 와 같다. `tokenize` 가 준 `Cow` 목록도 받으려고 제네릭으로 둔다.
fn longest_of<S: AsRef<str>>(words: &[S]) -> Option<&str> {
    let mut best: Option<&str> = None;
    for w in words {
        best = Some(match best {
            None => w.as_ref(),
            Some(b) => longer(b, w.as_ref()),
        });
    }
    best
}

pub fn top_n(counts: &HashMap<String, usize>, n: usize) -> Vec<(String, usize)> {
    let mut items: Vec<(&str, usize)> = counts.iter().map(|(w, c)| (w.as_str(), *c)).collect();
    items.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(b.0)));
    items.truncate(n);
    items.into_iter().map(|(w, c)| (w.to_string(), c)).collect()
}

pub fn summary(text: &str, top: usize, min: usize) -> String {
    let words = tokenize(text);
    let mut counts = count(&words);
    drop_rare(&mut counts, min);
    let mut lines: Vec<String> = vec![
        format!("words: {}", words.len()),
        format!("unique: {}", counts.len()),
        format!("longest: {}", longest_of(&words).unwrap_or("-")),
    ];
    for (w, n) in top_n(&counts, top) {
        lines.push(format!("{n}\t{w}"));
    }
    lines.join("\n")
}
