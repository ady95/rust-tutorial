use std::collections::HashMap;

// Python 습관: dict를 돌면서 그 dict에서 항목을 지운다
pub fn drop_rare(counts: &mut HashMap<String, usize>, min: usize) {
    for (word, n) in counts.iter() {
        if *n < min {
            counts.remove(word);
        }
    }
}
