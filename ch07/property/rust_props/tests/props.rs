//! Python 없이 Rust 구현만으로 확인할 수 있는 성질 (07-2).
//! 기대 출력을 몰라도 "어떤 입력에서도 지켜져야 하는 것"은 검사할 수 있다.

use proptest::prelude::*;
use wordfreq::{count_words, tokenize};

proptest! {
    /// 어떤 문자열을 넣어도 멈추지(panic) 않는다
    #[test]
    fn tokenize_never_panics(text in any::<String>()) {
        let _ = tokenize(&text);
    }

    /// 단어에는 공백이 없고 빈 단어도 없다
    #[test]
    fn words_are_nonempty_without_whitespace(text in any::<String>()) {
        for word in tokenize(&text) {
            prop_assert!(!word.is_empty());
            prop_assert!(!word.chars().any(char::is_whitespace));
        }
    }

    /// 빈도를 모두 더하면 전체 단어 수, 항목 수는 서로 다른 단어 수
    #[test]
    fn counts_add_up(text in any::<String>()) {
        let words = tokenize(&text);
        let report = count_words(&words, usize::MAX);
        let sum: usize = report.top.iter().map(|(_, n)| *n).sum();
        prop_assert_eq!(sum, report.total_words);
        prop_assert_eq!(report.top.len(), report.unique_words);
    }

    /// 빈도 내림차순, 같으면 단어 오름차순
    #[test]
    fn top_is_sorted(text in any::<String>()) {
        let report = count_words(&tokenize(&text), usize::MAX);
        for pair in report.top.windows(2) {
            let ((wa, na), (wb, nb)) = (&pair[0], &pair[1]);
            prop_assert!(na > nb || (na == nb && wa < wb));
        }
    }

    /// Σ 바로 앞에 아무 글자 하나를 둔다. 어말 시그마 규칙이 앞 글자를 보는 곳을 집중해서 시험한다
    #[test]
    fn sigma_after_any_char_never_panics(c in any::<char>()) {
        let _ = tokenize(&format!("{c}Σ"));
    }

    /// 이미 소문자로 정리된 단어를 다시 넣으면 같은 단어가 나온다
    #[test]
    fn tokenize_is_idempotent(text in any::<String>()) {
        let once = tokenize(&text);
        let twice = tokenize(&once.join(" "));
        prop_assert_eq!(once, twice);
    }
}
