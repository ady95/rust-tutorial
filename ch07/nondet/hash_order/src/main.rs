//! HashMap 을 그대로 돌며 출력하면 실행할 때마다 순서가 바뀌는지 확인한다 (07-4).

use std::collections::{BTreeMap, HashMap};

fn main() {
    let words = ["the", "cat", "and", "the", "hat", "sat", "on", "a", "mat"];
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for w in words {
        *counts.entry(w).or_insert(0) += 1;
    }
    let hash_order: Vec<&str> = counts.keys().copied().collect();
    let sorted: BTreeMap<&str, usize> = counts.into_iter().collect();
    let tree_order: Vec<&str> = sorted.keys().copied().collect();
    println!("hash: {}", hash_order.join(" "));
    println!("tree: {}", tree_order.join(" "));
}
