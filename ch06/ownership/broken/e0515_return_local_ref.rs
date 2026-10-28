// Python 습관: 함수 안에서 만든 문자열의 일부를 돌려준다
pub fn normalize(word: &str) -> &str {
    let lower = word.to_lowercase();
    lower.trim_matches(|c: char| c.is_ascii_punctuation())
}
