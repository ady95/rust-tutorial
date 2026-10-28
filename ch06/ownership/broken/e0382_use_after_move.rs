// Python 습관: 리스트를 함수에 넘긴 뒤에도 그대로 다시 쓴다
fn count_words(words: Vec<String>) -> usize {
    words.len()
}

pub fn report(text: &str) -> String {
    let words: Vec<String> = text.split_whitespace().map(|w| w.to_lowercase()).collect();
    let total = count_words(words);
    let first = &words[0];
    format!("{total} {first}")
}
