//! wordstats — 단어 통계. python_src/wordstats.py 와 같은 출력을 낸다.

use std::borrow::Cow;
use std::collections::HashMap;

/// 앞뒤 ASCII 문장부호를 떼고 소문자로 바꾼다. 바꿀 글자가 없으면 입력을 빌려 쓴다.
/// 소문자 변환은 ASCII 문장부호를 만들거나 없애지 않으므로 Python 과 순서가 달라도 결과가 같다.
pub fn normalize(word: &str) -> Cow<'_, str> {
    let trimmed = word.trim_matches(|c: char| c.is_ascii_punctuation());
    if trimmed.chars().all(|c| c.to_lowercase().eq([c])) {
        Cow::Borrowed(trimmed)
    } else {
        Cow::Owned(trimmed.to_lowercase())
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

/// 키 String 은 처음 나온 단어에만 만든다.
pub fn count<S: AsRef<str>>(words: &[S]) -> HashMap<String, usize> {
    let mut counts: HashMap<String, usize> = HashMap::new();
    for w in words {
        let w = w.as_ref();
        match counts.get_mut(w) {
            Some(n) => *n += 1,
            None => {
                counts.insert(w.to_string(), 1);
            }
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

/// `longest` 의 본체. `tokenize` 결과(`Cow`)에도 쓰려고 나눴다.
/// 공개 `longest` 를 제네릭으로 바꾸면 `longest(&[])` 의 타입을 추론할 수 없다.
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
    let mut items: Vec<(&String, &usize)> = counts.iter().collect();
    items.sort_by(|a, b| b.1.cmp(a.1).then_with(|| a.0.cmp(b.0)));
    items.truncate(n);
    // 잘라 낸 뒤에만 복사한다.
    items.into_iter().map(|(w, c)| (w.clone(), *c)).collect()
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
