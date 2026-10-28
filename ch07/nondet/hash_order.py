"""Python dict 와 set 을 그대로 돌며 출력한다. hash_order(Rust)와 같은 단어를 쓴다 (07-4)."""

words = ["the", "cat", "and", "the", "hat", "sat", "on", "a", "mat"]
counts: dict[str, int] = {}
for w in words:
    counts[w] = counts.get(w, 0) + 1
print("dict:", " ".join(counts))
print("set: ", " ".join(set(words)))
