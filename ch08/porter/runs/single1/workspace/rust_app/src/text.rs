//! 단어 규칙(계약 2절)과 집계·정렬(계약 3절). 기준 구현의 tokenize, count_words 에 해당한다.

use std::collections::HashMap;

/// 단어 앞뒤에서 떼어 낼 문장 부호. 단어 가운데 있는 것은 남긴다 (don't, e-mail).
pub const PUNCTUATION: &str = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~“”‘’…·";

/// Python str.split()(인자 없음)이 공백으로 보는 글자. Python 3.12(Unicode 15.0)의 str.isspace 와 같다.
/// char::is_whitespace 는 U+001C–U+001F 를 공백으로 보지 않으므로 쓰지 않는다.
pub fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}'..='\u{d}'
            | '\u{1c}'..='\u{20}'
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

/// Unicode 15.0(Python 3.12)에는 없고 Rust std 의 Unicode(17.0)에서 대소문자가 있는 글자로 들어온 것.
/// Python 은 이 글자를 바꾸지 않고, 대소문자가 없는 글자로 본다(Final_Sigma 문맥도 여기서 끊긴다).
const NEWER_CASED: &[(char, char)] = &[
    ('\u{1c89}', '\u{1c8a}'),   // 16.0 Cyrillic TJE
    ('\u{a7cb}', '\u{a7cf}'),   // 16.0, 17.0 Latin Extended-D
    ('\u{a7d2}', '\u{a7d2}'),   // 17.0 CAPITAL DOUBLE THORN
    ('\u{a7d4}', '\u{a7d4}'),   // 17.0 CAPITAL DOUBLE WYNN
    ('\u{a7da}', '\u{a7dc}'),   // 16.0 LAMBDA
    ('\u{a7f1}', '\u{a7f1}'),   // 17.0 MODIFIER LETTER CAPITAL S
    ('\u{10d50}', '\u{10d65}'), // 16.0 Garay capital
    ('\u{10d70}', '\u{10d85}'), // 16.0 Garay small
    ('\u{16ea0}', '\u{16eb8}'), // 17.0 Beria Erfe capital
    ('\u{16ebb}', '\u{16ed3}'), // 17.0 Beria Erfe small
];

fn is_newer_cased(c: char) -> bool {
    NEWER_CASED.iter().any(|&(lo, hi)| lo <= c && c <= hi)
}

/// Python str.lower() 와 같은 소문자 변환.
///
/// str::to_lowercase 도 완전 매핑과 Final_Sigma 를 구현한다. Unicode 15.0 이후 글자에서 끊어 각 조각만 바꾸면,
/// Python 이 그 글자를 "대소문자 없음, 무시 가능 아님"으로 보는 것과 같은 결과가 된다.
pub fn py_lower(word: &str) -> String {
    let mut out = String::with_capacity(word.len());
    let mut start = 0;
    for (i, c) in word.char_indices() {
        if is_newer_cased(c) {
            out.push_str(&word[start..i].to_lowercase());
            out.push(c);
            start = i + c.len_utf8();
        }
    }
    out.push_str(&word[start..].to_lowercase());
    out
}

/// 공백(str.split 기준)으로 자르고, 앞뒤 문장 부호를 떼고, 소문자로 바꾼다.
pub fn tokenize(text: &str) -> Vec<String> {
    text.split(is_py_space)
        .map(|raw| py_lower(raw.trim_matches(|c| PUNCTUATION.contains(c))))
        .filter(|word| !word.is_empty())
        .collect()
}

#[derive(Debug, PartialEq, Eq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, usize)>,
}

/// 빈도 내림차순, 같은 빈도는 단어 오름차순(코드 포인트 순)으로 상위 top_n 개.
pub fn count_words(words: Vec<String>, top_n: usize) -> Report {
    let total_words = words.len();
    let mut counter: HashMap<String, usize> = HashMap::new();
    for word in words {
        *counter.entry(word).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(String, usize)> = counter.into_iter().collect();
    // String 의 Ord 는 UTF-8 바이트 순이고, 이는 코드 포인트 순과 같다. 키가 유일하므로 안정 정렬이 필요 없다
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    ranked.truncate(top_n);
    Report {
        total_words,
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
    fn strips_punctuation_and_lowercases() {
        assert_eq!(
            words("\"Hello,\" Don't e-mail... RUST!"),
            ["hello", "don't", "e-mail", "rust"]
        );
        assert!(words("!!! --- ...").is_empty());
        assert_eq!(words("“Quote” ‘x’ …end· ·"), ["quote", "x", "end"]);
    }

    #[test]
    fn splits_on_python_whitespace() {
        // U+001C–U+001F, U+000B, U+0085, U+3000 은 Python 공백
        assert_eq!(words("a\u{1c}b a\u{1f}b"), ["a", "b", "a", "b"]);
        assert_eq!(
            words("a\u{b}b a\u{85}b a\u{3000}b"),
            ["a", "b", "a", "b", "a", "b"]
        );
        // U+200B, U+180E, U+FEFF 는 공백이 아니다
        assert_eq!(words("a\u{200b}b a\u{180e}b"), ["a\u{200b}b", "a\u{180e}b"]);
        assert_eq!(words("\u{feff}hello hello"), ["\u{feff}hello", "hello"]);
        assert_eq!(words("a\rb a\0b"), ["a", "b", "a\0b"]);
    }

    #[test]
    fn lower_matches_python_special_cases() {
        assert_eq!(py_lower("İ"), "i\u{307}");
        assert_eq!(py_lower("ΑΣ"), "ας");
        assert_eq!(py_lower("Σ"), "σ");
        assert_eq!(py_lower("ΑΣΑ"), "ασα");
        assert_eq!(py_lower("ΑΣ'Β"), "ασ'β");
        assert_eq!(py_lower("ΆΣ"), "άς");
        assert_eq!(py_lower("ΑΣ\u{301}"), "ας\u{301}");
    }

    #[test]
    fn lower_leaves_letters_newer_than_unicode_15() {
        assert_eq!(py_lower("\u{1c89}"), "\u{1c89}");
        assert_eq!(py_lower("\u{a7cb}\u{a7dc}A"), "\u{a7cb}\u{a7dc}a");
        assert_eq!(py_lower("\u{10d50}"), "\u{10d50}");
        // Python 에서 새 글자는 대소문자가 없는 글자이므로 Σ 의 문맥을 끊는다
        assert_eq!(py_lower("Σ\u{10d70}"), "σ\u{10d70}");
        assert_eq!(py_lower("AΣ\u{10d70}"), "aς\u{10d70}");
    }

    #[test]
    fn ties_are_sorted_by_code_point() {
        let input = ["b", "a", "c", "b", "a", "c", "d"]
            .map(String::from)
            .to_vec();
        let report = count_words(input, 10);
        let top: Vec<(&str, usize)> = report.top.iter().map(|(w, c)| (w.as_str(), *c)).collect();
        assert_eq!(top, [("a", 2), ("b", 2), ("c", 2), ("d", 1)]);
        let report = count_words(words("z é e 😀 \u{fffd}"), usize::MAX);
        let order: Vec<&str> = report.top.iter().map(|(w, _)| w.as_str()).collect();
        assert_eq!(order, ["e", "z", "é", "\u{fffd}", "😀"]);
    }
}
