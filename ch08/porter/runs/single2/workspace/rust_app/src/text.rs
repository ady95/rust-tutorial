//! 단어 규칙(계약 2절)과 집계. Unicode 판단은 모두 기준 구현의 Python(Unicode 15.0) 에서 뽑은 표를 쓴다.

use std::cmp::Ordering;
use std::collections::HashMap;

use crate::unicode_tables::{DECIMAL, LOWER, LOWER_MULTI, SIGMA_CASED, SIGMA_SKIP, SPACE};

/// 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
pub const PUNCTUATION: &str = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~“”‘’…·";

const CAPITAL_SIGMA: char = '\u{03A3}';

#[derive(Debug, PartialEq, Eq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, usize)>,
}

fn in_ranges(table: &[(u32, u32)], c: char) -> bool {
    let c = c as u32;
    table
        .binary_search_by(|&(start, end)| {
            if end < c {
                Ordering::Less
            } else if start > c {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        })
        .is_ok()
}

/// Python str.isspace() (str.split() 이 자르는 기준)
pub fn is_space(c: char) -> bool {
    in_ranges(SPACE, c)
}

/// Python 정규식 \d (str 패턴)
pub fn is_decimal(c: char) -> bool {
    in_ranges(DECIMAL, c)
}

fn push_lower(c: char, out: &mut String) {
    let cp = c as u32;
    if let Ok(i) = LOWER_MULTI.binary_search_by_key(&cp, |&(k, _)| k) {
        out.push_str(LOWER_MULTI[i].1);
        return;
    }
    let mapped = LOWER
        .binary_search_by(|&(start, end, _, _)| {
            if end < cp {
                Ordering::Less
            } else if start > cp {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        })
        .ok()
        .and_then(|i| {
            let (start, _, step, delta) = LOWER[i];
            if (cp - start).is_multiple_of(step) {
                char::from_u32(cp.wrapping_add_signed(delta))
            } else {
                None
            }
        });
    out.push(mapped.unwrap_or(c));
}

/// CPython handle_capital_sigma 와 같은 Final_Sigma 판단
fn is_final_sigma(chars: &[char], i: usize) -> bool {
    let skip = |c: &&char| in_ranges(SIGMA_SKIP, **c);
    let cased = |c: &char| in_ranges(SIGMA_CASED, *c);
    let before = chars[..i].iter().rev().find(|c| !skip(c));
    if !before.is_some_and(cased) {
        return false;
    }
    let after = chars[i + 1..].iter().find(|c| !skip(c));
    !after.is_some_and(cased)
}

/// Python str.lower() 와 같은 소문자 변환
pub fn py_lower(word: &str) -> String {
    let chars: Vec<char> = word.chars().collect();
    let mut out = String::with_capacity(word.len());
    for (i, &c) in chars.iter().enumerate() {
        if c == CAPITAL_SIGMA {
            out.push(if is_final_sigma(&chars, i) {
                '\u{03C2}'
            } else {
                '\u{03C3}'
            });
        } else {
            push_lower(c, &mut out);
        }
    }
    out
}

/// 공백(str.split 기준)으로 자르고, 앞뒤 문장 부호를 떼고, 소문자로 바꾼다.
pub fn tokenize(text: &str) -> Vec<String> {
    text.split(is_space)
        .map(|raw| raw.trim_matches(|c| PUNCTUATION.contains(c)))
        .filter(|word| !word.is_empty())
        .map(py_lower)
        .collect()
}

/// 빈도 내림차순, 같은 빈도는 단어 오름차순(코드 포인트 순)으로 상위 top_n 개.
pub fn count_words(words: &[String], top_n: usize) -> Report {
    let mut counter: HashMap<&str, usize> = HashMap::new();
    for word in words {
        *counter.entry(word.as_str()).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(String, usize)> = counter
        .into_iter()
        .map(|(word, count)| (word.to_string(), count))
        .collect();
    // String 의 순서는 UTF-8 바이트 순이고, 이는 코드 포인트 순과 같다
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    ranked.truncate(top_n);
    Report {
        total_words: words.len(),
        unique_words,
        top: ranked,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words(text: &str) -> Vec<String> {
        tokenize(text)
    }

    #[test]
    fn splits_on_python_whitespace() {
        // U+001C-U+001F, U+000B, U+0085, U+3000 은 Python 에서 공백, U+200B·U+180E 는 아니다
        assert_eq!(words("a\u{1c}b a\u{1f}b"), ["a", "b", "a", "b"]);
        assert_eq!(
            words("a\u{0b}b a\u{85}b a\u{3000}b"),
            ["a", "b", "a", "b", "a", "b"]
        );
        assert_eq!(words("a\u{200b}b a\u{180e}b"), ["a\u{200b}b", "a\u{180e}b"]);
    }

    #[test]
    fn strips_only_edges() {
        assert_eq!(
            words("“Don't” (e-mail)… ·x· --- '"),
            ["don't", "e-mail", "x"]
        );
    }

    #[test]
    fn keeps_bom_and_control_chars() {
        assert_eq!(words("\u{feff}hello hello"), ["\u{feff}hello", "hello"]);
        assert_eq!(words("a\0b a\u{8}b a\rb"), ["a\0b", "a\u{8}b", "a", "b"]);
    }

    #[test]
    fn lower_matches_python() {
        // 기대값은 Python 3.12.3 의 str.lower() 결과
        assert_eq!(py_lower("İ"), "i\u{307}");
        assert_eq!(py_lower("ΑΣ"), "ας");
        assert_eq!(py_lower("Σ"), "σ");
        assert_eq!(py_lower("ΑΣΑ"), "ασα");
        assert_eq!(py_lower("ΑΣ'Β"), "ασ'β");
        assert_eq!(py_lower("ΆΣ"), "άς");
        assert_eq!(py_lower("ΑΣ\u{301}"), "ας\u{301}");
        // Unicode 16.0 에서 생긴 대소문자 쌍은 Python 3.12(Unicode 15.0)에서 바뀌지 않는다
        assert_eq!(
            py_lower("\u{A7CB}\u{10D50}\u{1C89}"),
            "\u{A7CB}\u{10D50}\u{1C89}"
        );
    }

    #[test]
    fn ranks_by_count_then_code_point() {
        let report = count_words(&words("z é e z b b"), 10);
        assert_eq!(report.total_words, 6);
        assert_eq!(report.unique_words, 4);
        let top: Vec<(&str, usize)> = report.top.iter().map(|(w, c)| (w.as_str(), *c)).collect();
        assert_eq!(top, [("b", 2), ("z", 2), ("e", 1), ("é", 1)]);
        assert_eq!(count_words(&words("a b c"), 2).top.len(), 2);
        assert_eq!(count_words(&words("a b c"), usize::MAX).top.len(), 3);
    }

    #[test]
    fn decimal_digits() {
        assert!(is_decimal('5'));
        assert!(is_decimal('\u{663}'));
        assert!(!is_decimal('²'));
    }
}
