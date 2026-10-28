//! tests/cases.json 의 케이스를 실행 파일로 돌려 계약(contracts/behavior_spec.md)과 바이트 단위로 비교한다.
//! 기대값은 Python 기준 구현의 테스트(tests/test_wordfreq.py)와 픽스처에서 옮겼다.

use std::path::Path;
use std::process::{Command, Output};

fn run(args: &[&str]) -> Output {
    // automation/compare.py 처럼 프로젝트 루트에서 실행한다.
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    Command::new(env!("CARGO_BIN_EXE_wordfreq")).args(args).current_dir(root).output().unwrap()
}

fn assert_ok(args: &[&str], stdout: &str) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(0), "{args:?}");
    assert_eq!(String::from_utf8(out.stdout).unwrap(), stdout, "{args:?}");
    assert!(out.stderr.is_empty(), "{args:?}");
}

fn assert_input_error(args: &[&str], stderr: &str) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(1), "{args:?}");
    assert!(out.stdout.is_empty(), "{args:?}");
    assert_eq!(String::from_utf8(out.stderr).unwrap(), stderr, "{args:?}");
}

fn assert_usage_error(args: &[&str]) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(2), "{args:?}");
    assert!(out.stdout.is_empty(), "{args:?}");
    assert!(!out.stderr.is_empty(), "{args:?}");
}

const BASIC: &str = "words: 10\nunique: 6\n3\trust\n2\tis\n2\tpython\n1\tand\n1\tfast\n1\tfriendly\n";

#[test]
fn basic() {
    assert_ok(&["tests/fixtures/basic.txt"], BASIC);
}

#[test]
fn basic_top2() {
    assert_ok(&["tests/fixtures/basic.txt", "--top", "2"], "words: 10\nunique: 6\n3\trust\n2\tis\n");
}

#[test]
fn basic_json() {
    assert_ok(
        &["tests/fixtures/basic.txt", "--json"],
        "{\"words\":10,\"unique\":6,\"top\":[{\"word\":\"rust\",\"count\":3},{\"word\":\"is\",\"count\":2},\
         {\"word\":\"python\",\"count\":2},{\"word\":\"and\",\"count\":1},{\"word\":\"fast\",\"count\":1},\
         {\"word\":\"friendly\",\"count\":1}]}\n",
    );
}

#[test]
fn korean() {
    assert_ok(
        &["tests/fixtures/korean.txt"],
        "words: 12\nunique: 11\n2\t러스트는\n1\tpython\n1\trust와\n1\t러스트로\n1\t만들고\n\
         1\t빠르다\n1\t쉽다\n1\t옮긴다\n1\t컴파일한다\n1\t파이썬으로\n",
    );
}

#[test]
fn korean_json() {
    assert_ok(
        &["tests/fixtures/korean.txt", "--json", "--top", "3"],
        "{\"words\":12,\"unique\":11,\"top\":[\
         {\"word\":\"러스트는\",\"count\":2},{\"word\":\"python\",\"count\":1},{\"word\":\"rust와\",\"count\":1}]}\n",
    );
}

#[test]
fn punctuation() {
    assert_ok(
        &["tests/fixtures/punctuation.txt", "--top", "20"],
        "words: 12\nunique: 12\n1\tdon't\n1\tdot\n1\te-mail\n1\thello\n1\tme\n1\tplease\n\
         1\tquoted\n1\tsaid\n1\tshe\n1\tsingle\n1\tstop\n1\twait\n",
    );
}

#[test]
fn ties() {
    assert_ok(&["tests/fixtures/ties.txt"], "words: 7\nunique: 4\n2\ta\n2\tb\n2\tc\n1\td\n");
}

#[test]
fn crlf_case() {
    assert_ok(
        &["tests/fixtures/crlf_case.txt", "--json"],
        "{\"words\":6,\"unique\":4,\"top\":[{\"word\":\"upper\",\"count\":3},\
         {\"word\":\"endings\",\"count\":1},{\"word\":\"line\",\"count\":1},{\"word\":\"windows\",\"count\":1}]}\n",
    );
}

#[test]
fn empty() {
    assert_ok(&["tests/fixtures/empty.txt"], "words: 0\nunique: 0\n");
    assert_ok(&["tests/fixtures/empty.txt", "--json"], "{\"words\":0,\"unique\":0,\"top\":[]}\n");
}

#[test]
fn input_errors() {
    assert_input_error(
        &["tests/fixtures/no_such_file.txt"],
        "wordfreq: error: file not found: tests/fixtures/no_such_file.txt\n",
    );
    assert_input_error(
        &["tests/fixtures/invalid_utf8.txt"],
        "wordfreq: error: not valid UTF-8: tests/fixtures/invalid_utf8.txt\n",
    );
    assert_input_error(&["tests/fixtures"], "wordfreq: error: cannot read file: tests/fixtures\n");
}

#[test]
fn usage_errors() {
    assert_usage_error(&[]);
    assert_usage_error(&["tests/fixtures/basic.txt", "--top", "0"]);
    assert_usage_error(&["tests/fixtures/basic.txt", "--top", "abc"]);
    assert_usage_error(&["tests/fixtures/basic.txt", "--bogus"]);
}

#[test]
fn paths_are_opened_like_pathlib() {
    // Path("") 는 "." (디렉터리), Path("a.txt/") 는 a.txt 이다.
    assert_input_error(&[""], "wordfreq: error: cannot read file: \n");
    assert_ok(&["tests/fixtures/basic.txt/"], BASIC);
    assert_ok(&["tests/./fixtures//basic.txt"], BASIC);
}

#[test]
fn help_goes_to_stdout() {
    let out = run(&["--help"]);
    assert_eq!(out.status.code(), Some(0));
    assert!(String::from_utf8(out.stdout).unwrap().starts_with("usage: wordfreq [-h] [--top TOP] [--json] file\n"));
    assert!(out.stderr.is_empty());
}
