"""깨진 task/src/lib.rs 에서 컴파일 오류 6개만 최소한으로 고친 버전을 만든다 (06-3).

동작 버그(merge·top_n)와 Clippy 경고 거리(longest·top_n)는 그대로 둔다.
컴파일만 통과시키면 무엇이 남는지 보려는 것이다.
사용법: python3 compile_only_fix.py <출력 lib.rs>
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

REPLACEMENTS = [
    # E0515: 지역 String 을 빌린 &str 대신 String 을 돌려준다
    (
        "pub fn normalize(word: &str) -> &str {\n    let lower = word.to_lowercase();\n"
        "    lower.trim_matches(|c: char| c.is_ascii_punctuation())\n}",
        "pub fn normalize(word: &str) -> String {\n    let lower = word.to_lowercase();\n"
        "    lower.trim_matches(|c: char| c.is_ascii_punctuation()).to_string()\n}",
    ),
    ("        .map(str::to_string)\n", ""),
    # E0382: count 가 빌리도록 (테스트도 count(&...) 로 부른다)
    ("pub fn count(words: Vec<String>)", "pub fn count(words: &[String])"),
    ("*counts.entry(w).or_insert(0) += 1;", "*counts.entry(w.clone()).or_insert(0) += 1;"),
    ("let mut counts = count(words);", "let mut counts = count(&words);"),
    # E0502: retain
    (
        "    for (word, n) in counts.iter() {\n        if *n < min {\n            counts.remove(word);\n        }\n    }\n",
        "    counts.retain(|_, n| *n >= min);\n",
    ),
    # E0499: 가변 빌림이 겹치지 않게만 고친다. source 를 0 으로 남기는 원래 동작은 그대로 둔다
    (
        "    if let Some(src) = counts.get_mut(source) {\n"
        "        let dst = counts.entry(target.to_string()).or_insert(0);\n"
        "        *dst += *src;\n        *src = 0;\n    }\n",
        "    if let Some(n) = counts.get(source).copied() {\n"
        "        *counts.entry(target.to_string()).or_insert(0) += n;\n"
        "        counts.insert(source.to_string(), 0);\n    }\n",
    ),
    # E0106
    ("pub fn longer(a: &str, b: &str) -> &str {", "pub fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {"),
    # E0597: Vec<String> 에 모은다
    ("let mut lines: Vec<&str> = vec![header.as_str()];", "let mut lines: Vec<String> = vec![header];"),
    ("        let line = format!(\"{n}\\t{w}\");\n        lines.push(line.as_str());\n",
     "        lines.push(format!(\"{n}\\t{w}\"));\n"),
]


def main() -> int:
    src = (HERE / "task" / "src" / "lib.rs").read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in src:
            print(f"패턴을 찾지 못함: {old[:60]!r}", file=sys.stderr)
            return 1
        src = src.replace(old, new)
    Path(sys.argv[1]).write_text(src, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
