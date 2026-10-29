use crate::py_tables::{in_table, SIGMA_CASED, SIGMA_IGNORABLE};
use std::collections::HashMap;

/// 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다.
const PUNCTUATION: &str = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~“”‘’…·";

/// Python 3.12(Unicode 15.0)의 str.lower() 가 바꾸지 않는데 Rust 쪽이 바꾸는 글자.
/// verify/lower_table.py 의 전수 비교로 확정한다.
fn is_lower_exception(c: char) -> bool {
    matches!(
        c,
        '\u{1C89}'
            | '\u{A7CB}'
            | '\u{A7CC}'
            | '\u{A7CE}'
            | '\u{A7D2}'
            | '\u{A7D4}'
            | '\u{A7DA}'
            | '\u{A7DC}'
            | '\u{10D50}'..='\u{10D65}'
            | '\u{16EA0}'..='\u{16EB8}'
    )
}

pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, u64)>,
}

/// Python str.split() 이 공백으로 보는 글자(Py_UNICODE_ISSPACE)
pub fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}'..='\u{D}'
            | '\u{1C}'..='\u{1F}'
            | ' '
            | '\u{85}'
            | '\u{A0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200A}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202F}'
            | '\u{205F}'
            | '\u{3000}'
    )
}

/// Python 의 Final_Sigma: 앞에 (건너뛰는 글자를 빼고) Cased 글자가 있고 뒤에는 없을 때
fn is_final_sigma(before: &[char], after: &[char]) -> bool {
    let skip = |c: &char| in_table(SIGMA_IGNORABLE, *c);
    let cased_before = before
        .iter()
        .rev()
        .find(|c| !skip(c))
        .is_some_and(|&c| in_table(SIGMA_CASED, c));
    let cased_after = after
        .iter()
        .find(|c| !skip(c))
        .is_some_and(|&c| in_table(SIGMA_CASED, c));
    cased_before && !cased_after
}

pub fn py_lower(word: &str) -> String {
    let chars: Vec<char> = word.chars().collect();
    let mut out = String::with_capacity(word.len());
    for (i, &c) in chars.iter().enumerate() {
        if c == '\u{3A3}' {
            let final_sigma = is_final_sigma(&chars[..i], &chars[i + 1..]);
            out.push(if final_sigma { '\u{3C2}' } else { '\u{3C3}' });
        } else if is_lower_exception(c) {
            out.push(c);
        } else {
            out.extend(c.to_lowercase());
        }
    }
    out
}

pub fn tokenize(text: &str) -> Vec<String> {
    text.split(is_py_space)
        .filter(|raw| !raw.is_empty())
        .map(|raw| py_lower(raw.trim_matches(|c| PUNCTUATION.contains(c))))
        .filter(|word| !word.is_empty())
        .collect()
}

pub fn count_words(words: &[String], top_n: usize) -> Report {
    let mut counter: HashMap<&str, u64> = HashMap::new();
    for word in words {
        *counter.entry(word.as_str()).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(String, u64)> = counter
        .into_iter()
        .map(|(word, count)| (word.to_string(), count))
        .collect();
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    ranked.truncate(top_n.min(ranked.len()));
    Report {
        total_words: words.len(),
        unique_words,
        top: ranked,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tok(s: &str) -> Vec<String> {
        tokenize(s)
    }

    #[test]
    fn splits_on_python_whitespace() {
        assert_eq!(tok("a\x1cb a\x1fb"), ["a", "b", "a", "b"]);
        assert_eq!(tok("a\x0bb"), ["a", "b"]);
        assert_eq!(tok("a\u{3000}b a\u{85}b"), ["a", "b", "a", "b"]);
        assert_eq!(tok("a\u{200b}b"), ["a\u{200b}b"]);
        assert_eq!(tok("a\u{180e}b"), ["a\u{180e}b"]);
    }

    #[test]
    fn strips_punctuation_and_lowercases() {
        assert_eq!(tok("“Don't,” e-mail… ·x·"), ["don't", "e-mail", "x"]);
        assert_eq!(tok("!!! ..."), Vec::<String>::new());
    }

    #[test]
    fn bom_is_kept() {
        assert_eq!(tok("\u{feff}hello hello").len(), 2);
    }

    #[test]
    fn final_sigma_and_special_casing() {
        assert_eq!(py_lower("ΑΣ"), "ας");
        assert_eq!(py_lower("Σ"), "σ");
        assert_eq!(py_lower("ΑΣΑ"), "ασα");
        assert_eq!(py_lower("İ"), "i\u{307}");
        assert_eq!(py_lower("ΑΣ'Β"), "ασ'β");
        assert_eq!(py_lower("ΆΣ"), "άς");
        assert_eq!(py_lower("ΑΣ\u{301}"), "ας\u{301}");
        // 새 Rust 와 Python 15.0 의 Cased 판정이 다른 글자(sigma_context.py 가 찾음)
        assert_eq!(py_lower("\u{295}Σ"), "\u{295}ς");
        // Python 3.12(Unicode 15.0)에서는 바뀌지 않는 글자
        assert_eq!(py_lower("\u{A7CB}\u{10D50}Σ"), "\u{A7CB}\u{10D50}σ");
    }

    #[test]
    fn ranking_and_truncation() {
        let words = tok("b a b é z");
        let report = count_words(&words, usize::MAX);
        assert_eq!(report.total_words, 5);
        assert_eq!(report.unique_words, 4);
        let order: Vec<&str> = report.top.iter().map(|(w, _)| w.as_str()).collect();
        assert_eq!(order, ["b", "a", "z", "é"]);
        assert_eq!(count_words(&words, 2).top.len(), 2);
    }
}
