//! broken/ 의 예제 6개를 고친 버전 (06-1). 각 함수 위 주석은 대응하는 오류 코드와 고친 방법.

use std::collections::HashMap;

// E0382: 소유권을 넘기지 않고 빌려준다 (&[String])
fn count_words(words: &[String]) -> usize {
    words.len()
}

pub fn report(text: &str) -> String {
    let words: Vec<String> = text.split_whitespace().map(|w| w.to_lowercase()).collect();
    let total = count_words(&words);
    let first = &words[0];
    format!("{total} {first}")
}

// E0502: 돌면서 지우지 않고, 남길 조건을 retain에 넘긴다
pub fn drop_rare(counts: &mut HashMap<String, usize>, min: usize) {
    counts.retain(|_, n| *n >= min);
}

// E0499: 가변 빌림을 하나씩 끝낸다
pub fn bump_pair(counts: &mut HashMap<String, usize>, a: &str, b: &str) {
    *counts.entry(a.to_string()).or_insert(0) += 1;
    *counts.entry(b.to_string()).or_insert(0) += 1;
}

// E0106: 반환값이 a, b 둘 다에서 올 수 있음을 수명 매개변수로 적는다
pub fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {
    if b.chars().count() > a.chars().count() {
        b
    } else {
        a
    }
}

// E0515: 함수 안에서 만든 값은 참조가 아니라 소유한 String으로 돌려준다
pub fn normalize(word: &str) -> String {
    word.to_lowercase()
        .trim_matches(|c: char| c.is_ascii_punctuation())
        .to_string()
}

// E0597: 반복문 밖까지 살아야 하는 값은 소유한 String으로 모은다
pub fn join_lower(lines: &[&str]) -> String {
    let mut out: Vec<String> = Vec::new();
    for line in lines {
        out.push(line.to_lowercase());
    }
    out.join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    // 기대값은 python_habits.py 의 출력과 같다
    #[test]
    fn report_keeps_words_usable() {
        assert_eq!(report("Apple banana apple"), "3 apple");
    }

    #[test]
    fn drop_rare_removes_below_min() {
        let mut counts = HashMap::from([
            ("apple".to_string(), 3),
            ("kiwi".to_string(), 1),
            ("pear".to_string(), 2),
        ]);
        drop_rare(&mut counts, 2);
        let mut kept: Vec<_> = counts.into_iter().collect();
        kept.sort();
        assert_eq!(
            kept,
            vec![("apple".to_string(), 3), ("pear".to_string(), 2)]
        );
    }

    #[test]
    fn bump_pair_same_key_twice() {
        let mut counts = HashMap::from([("a".to_string(), 1)]);
        bump_pair(&mut counts, "a", "a");
        assert_eq!(counts["a"], 3);
    }

    #[test]
    fn longer_prefers_first_on_tie() {
        assert_eq!(longer("ab", "abc"), "abc");
        assert_eq!(longer("ab", "cd"), "ab");
    }

    #[test]
    fn normalize_strips_ascii_punctuation() {
        assert_eq!(normalize("Hello!"), "hello");
    }

    #[test]
    fn join_lower_joins_with_space() {
        assert_eq!(join_lower(&["A B", "C"]), "a b c");
    }
}
