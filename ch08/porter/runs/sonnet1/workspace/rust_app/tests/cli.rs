use std::path::PathBuf;
use std::process::{Command, Output};

fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("wordfreq-{name}-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("basic.txt"), "the cat the hat\n").unwrap();
    dir
}

fn run(dir: &PathBuf, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_wordfreq"))
        .current_dir(dir)
        .args(args)
        .output()
        .unwrap()
}

#[test]
fn path_is_normalized_like_pathlib() {
    let dir = scratch("path");
    for arg in ["basic.txt", "basic.txt/", "basic.txt/.", "./basic.txt"] {
        let out = run(&dir, &[arg]);
        assert_eq!(out.status.code(), Some(0), "{arg}");
        assert_eq!(out.stdout, b"words: 4\nunique: 3\n2\tthe\n1\tcat\n1\that\n");
    }
}

#[test]
fn read_errors_are_classified() {
    let dir = scratch("errors");
    let missing = run(&dir, &["nope.txt/"]);
    assert_eq!(missing.status.code(), Some(1));
    assert_eq!(
        missing.stderr,
        b"wordfreq: error: file not found: nope.txt/\n"
    );
    let under_file = run(&dir, &["basic.txt/x"]);
    assert_eq!(
        under_file.stderr,
        b"wordfreq: error: cannot read file: basic.txt/x\n"
    );
    let empty = run(&dir, &[""]);
    assert_eq!(empty.status.code(), Some(1));
    assert_eq!(empty.stderr, b"wordfreq: error: cannot read file: \n");
}

#[test]
fn usage_errors_exit_2_with_empty_stdout() {
    let dir = scratch("usage");
    for args in [&[][..], &["basic.txt", "--top", "0"], &["-x.txt"]] {
        let out = run(&dir, args);
        assert_eq!(out.status.code(), Some(2), "{args:?}");
        assert!(out.stdout.is_empty() && !out.stderr.is_empty());
    }
}
