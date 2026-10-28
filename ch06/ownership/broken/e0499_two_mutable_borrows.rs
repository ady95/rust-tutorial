use std::collections::HashMap;

// Python 습관: 같은 dict의 두 칸을 각각 이름 붙여 잡아 두고 나중에 고친다
pub fn bump_pair(counts: &mut HashMap<String, usize>, a: &str, b: &str) {
    let x = counts.entry(a.to_string()).or_insert(0);
    let y = counts.entry(b.to_string()).or_insert(0);
    *x += 1;
    *y += 1;
}
