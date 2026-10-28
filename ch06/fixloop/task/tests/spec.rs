//! 명세 테스트. 기대값은 python_src/wordstats.py 의 출력이다. 이 파일은 고치지 않는다.

use std::collections::HashMap;
use std::io::Write;
use std::process::{Command, Stdio};
use wordstats::*;

const TEXT: &str = "The cat and the hat. The CAT sat!\nA hat, a bat; a mat?";

fn sorted(counts: HashMap<String, usize>) -> Vec<(String, usize)> {
    let mut items: Vec<_> = counts.into_iter().collect();
    items.sort();
    items
}

fn pairs(items: &[(&str, usize)]) -> Vec<(String, usize)> {
    items.iter().map(|(w, n)| (w.to_string(), *n)).collect()
}

#[test]
fn normalize_lowercases_and_strips_ascii_punctuation() {
    assert_eq!(normalize("Hello!"), "hello");
    assert_eq!(normalize("..."), "");
    assert_eq!(normalize("Don't"), "don't");
}

#[test]
fn tokenize_drops_empty_words() {
    let words = tokenize(TEXT);
    assert_eq!(words.len(), 14);
    assert_eq!(words[0], "the");
    assert_eq!(words[13], "mat");
}

#[test]
fn drop_rare_keeps_counts_at_or_above_min() {
    let mut counts = count(&tokenize(TEXT));
    drop_rare(&mut counts, 2);
    assert_eq!(
        sorted(counts),
        pairs(&[("a", 3), ("cat", 2), ("hat", 2), ("the", 3)])
    );
}

#[test]
fn merge_moves_count_and_removes_source() {
    let mut counts = count(&tokenize(TEXT));
    merge(&mut counts, "cat", "hat");
    assert_eq!(counts.get("hat"), Some(&4));
    assert_eq!(counts.get("cat"), None);
}

#[test]
fn merge_into_new_word() {
    let mut counts = count(&tokenize(TEXT));
    merge(&mut counts, "cat", "dog");
    assert_eq!(counts.get("dog"), Some(&2));
    assert_eq!(counts.get("cat"), None);
}

#[test]
fn merge_same_or_missing_word_changes_nothing() {
    let before = sorted(count(&tokenize(TEXT)));
    let mut counts = count(&tokenize(TEXT));
    merge(&mut counts, "cat", "cat");
    merge(&mut counts, "dog", "cat");
    assert_eq!(sorted(counts), before);
}

#[test]
fn top_n_breaks_ties_by_word() {
    let counts: HashMap<String, usize> = pairs(&[("b", 2), ("a", 2), ("c", 3), ("d", 1)])
        .into_iter()
        .collect();
    assert_eq!(top_n(&counts, 3), pairs(&[("c", 3), ("a", 2), ("b", 2)]));
}

#[test]
fn longest_prefers_first_on_tie() {
    let words: Vec<String> = ["ab", "cd", "abc", "xyz"].map(String::from).to_vec();
    assert_eq!(longest(&words), Some("abc"));
    assert_eq!(longest(&[]), None);
}

#[test]
fn summary_matches_python() {
    assert_eq!(
        summary(TEXT, 3, 1),
        "words: 14\nunique: 8\nlongest: the\n3\ta\n3\tthe\n2\tcat"
    );
    assert_eq!(
        summary(TEXT, 10, 2),
        "words: 14\nunique: 4\nlongest: the\n3\ta\n3\tthe\n2\tcat\n2\that"
    );
    assert_eq!(summary("", 5, 1), "words: 0\nunique: 0\nlongest: -");
    assert_eq!(
        summary("élan Élan ÉLAN zoo", 5, 1),
        "words: 4\nunique: 2\nlongest: élan\n3\télan\n1\tzoo"
    );
}

#[test]
fn cli_prints_summary_with_newline() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_wordstats"))
        .args(["--top", "3"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(TEXT.as_bytes())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success());
    assert_eq!(
        String::from_utf8(out.stdout).unwrap(),
        "words: 14\nunique: 8\nlongest: the\n3\ta\n3\tthe\n2\tcat\n"
    );
}

#[test]
fn cli_rejects_bad_number() {
    let out = Command::new(env!("CARGO_BIN_EXE_wordstats"))
        .args(["--top", "x"])
        .stdin(Stdio::null())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2));
}
