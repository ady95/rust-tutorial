//! 실행 파일 단위 테스트. 기대값은 tests/test_wordfreq.py 와 기준 구현(pathlib, argparse)의 동작에서 옮겼다.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn run(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_wordfreq"))
        .args(args)
        .current_dir(root())
        .output()
        .expect("failed to launch wordfreq")
}

const BASIC: &str =
    "words: 10\nunique: 6\n3\trust\n2\tis\n2\tpython\n1\tand\n1\tfast\n1\tfriendly\n";

fn assert_run(args: &[&str], code: i32, stdout: &str, stderr: &str) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(code), "{args:?}");
    assert_eq!(String::from_utf8_lossy(&out.stdout), stdout, "{args:?}");
    assert_eq!(String::from_utf8_lossy(&out.stderr), stderr, "{args:?}");
}

#[test]
fn basic_text_and_json() {
    assert_run(&["tests/fixtures/basic.txt"], 0, BASIC, "");
    assert_run(
        &["tests/fixtures/basic.txt", "--top", "2"],
        0,
        "words: 10\nunique: 6\n3\trust\n2\tis\n",
        "",
    );
    assert_run(
        &["tests/fixtures/korean.txt", "--json", "--top", "3"],
        0,
        "{\"words\":12,\"unique\":11,\"top\":[{\"word\":\"러스트는\",\"count\":2},{\"word\":\"python\",\"count\":1},{\"word\":\"rust와\",\"count\":1}]}\n",
        "",
    );
    assert_run(
        &["tests/fixtures/empty.txt", "--json"],
        0,
        "{\"words\":0,\"unique\":0,\"top\":[]}\n",
        "",
    );
}

#[test]
fn paths_are_normalized_like_pathlib() {
    assert_run(&["tests/fixtures/basic.txt/"], 0, BASIC, "");
    assert_run(&["tests/fixtures/basic.txt/."], 0, BASIC, "");
    assert_run(&["tests/fixtures/./basic.txt"], 0, BASIC, "");
    assert_run(&["--", "tests/fixtures/basic.txt"], 0, BASIC, "");
    assert_run(
        &["", "--top", "1"],
        1,
        "",
        "wordfreq: error: cannot read file: \n",
    );
}

#[test]
fn read_errors() {
    assert_run(
        &["no_such_file.txt"],
        1,
        "",
        "wordfreq: error: file not found: no_such_file.txt\n",
    );
    assert_run(
        &["nope.txt/"],
        1,
        "",
        "wordfreq: error: file not found: nope.txt/\n",
    );
    assert_run(&["-5"], 1, "", "wordfreq: error: file not found: -5\n");
    assert_run(
        &["tests/fixtures/invalid_utf8.txt"],
        1,
        "",
        "wordfreq: error: not valid UTF-8: tests/fixtures/invalid_utf8.txt\n",
    );
    assert_run(
        &["tests/fixtures/"],
        1,
        "",
        "wordfreq: error: cannot read file: tests/fixtures/\n",
    );
    assert_run(
        &["tests/fixtures/basic.txt/x"],
        1,
        "",
        "wordfreq: error: cannot read file: tests/fixtures/basic.txt/x\n",
    );
}

#[test]
fn usage_errors_and_help() {
    for args in [
        &[][..],
        &["tests/fixtures/basic.txt", "--top", "0"],
        &["tests/fixtures/basic.txt", "--top", "+3"],
        &["tests/fixtures/basic.txt", "--bogus"],
        &["tests/fixtures/basic.txt", "extra.txt"],
        &["tests/fixtures/basic.txt", "--json=1"],
        &["-x.txt"],
    ] {
        let out = run(args);
        assert_eq!(out.status.code(), Some(2), "{args:?}");
        assert!(out.stdout.is_empty(), "{args:?}");
        assert!(!out.stderr.is_empty(), "{args:?}");
    }
    let out = run(&["-h"]);
    assert_eq!(out.status.code(), Some(0));
    assert!(String::from_utf8_lossy(&out.stdout).starts_with("usage: wordfreq "));
}

#[cfg(target_os = "linux")]
#[test]
fn output_failure_exits_1() {
    let full = std::fs::File::create("/dev/full").expect("/dev/full");
    let out = Command::new(env!("CARGO_BIN_EXE_wordfreq"))
        .arg("tests/fixtures/basic.txt")
        .current_dir(root())
        .stdout(full)
        .output()
        .expect("failed to launch wordfreq");
    assert_eq!(out.status.code(), Some(1));
    assert_eq!(
        String::from_utf8_lossy(&out.stderr),
        "wordfreq: error: cannot write output\n"
    );
}
