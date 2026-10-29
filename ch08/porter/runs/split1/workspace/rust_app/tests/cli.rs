//! 실행 파일 통합 테스트 (위험 R4, R5, R7, R9, R12).
//! 기대값은 verify/probe_cli.py --show 로 Python 3.12.3 기준 구현을 실행한 결과에서 옮겼다.
//! 작업 폴더 루트(rust_app 의 상위)에서 실행해 tests/fixtures 를 쓴다.

use std::ffi::OsString;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};

const BASIC_ALL: &str =
    "words: 10\nunique: 6\n3\trust\n2\tis\n2\tpython\n1\tand\n1\tfast\n1\tfriendly\n";
const BASIC_TOP2: &str = "words: 10\nunique: 6\n3\trust\n2\tis\n";
const BASIC_JSON: &str = "{\"words\":10,\"unique\":6,\"top\":[{\"word\":\"rust\",\"count\":3},\
{\"word\":\"is\",\"count\":2},{\"word\":\"python\",\"count\":2},{\"word\":\"and\",\"count\":1},\
{\"word\":\"fast\",\"count\":1},{\"word\":\"friendly\",\"count\":1}]}\n";
const B: &[u8] = b"tests/fixtures/basic.txt";

fn root() -> PathBuf {
    let mut dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    dir.pop();
    dir
}

fn os(arg: &[u8]) -> OsString {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStringExt;
        OsString::from_vec(arg.to_vec())
    }
    #[cfg(not(unix))]
    {
        OsString::from(String::from_utf8_lossy(arg).into_owned())
    }
}

fn run(args: &[&[u8]]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_wordfreq"))
        .args(args.iter().map(|a| os(a)))
        .current_dir(root())
        .output()
        .expect("run wordfreq")
}

fn assert_ok(args: &[&[u8]], stdout: &str) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(0), "{args:?}");
    assert_eq!(String::from_utf8_lossy(&out.stdout), stdout, "{args:?}");
    assert!(out.stderr.is_empty(), "{args:?}");
}

fn assert_input_error(args: &[&[u8]], stderr: &str) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(1), "{args:?}");
    assert!(out.stdout.is_empty(), "{args:?}");
    assert_eq!(String::from_utf8_lossy(&out.stderr), stderr, "{args:?}");
}

fn assert_usage(args: &[&[u8]]) {
    let out = run(args);
    assert_eq!(out.status.code(), Some(2), "{args:?}");
    assert!(out.stdout.is_empty(), "{args:?}");
    assert!(!out.stderr.is_empty(), "{args:?}");
}

#[test]
fn r4_accepted_forms() {
    assert_ok(&[B, b"--to", b"2"], BASIC_TOP2);
    assert_ok(&[B, b"--t", b"2"], BASIC_TOP2);
    assert_ok(&[B, b"--t=2"], BASIC_TOP2);
    assert_ok(&[B, b"--to=2"], BASIC_TOP2);
    assert_ok(&[B, b"--js"], BASIC_JSON);
    assert_ok(&[B, b"--j"], BASIC_JSON);
    assert_ok(&[b"--top", b"2", B], BASIC_TOP2);
    assert_ok(&[b"--json", B], BASIC_JSON);
    assert_ok(&[B, b"--json", b"--json"], BASIC_JSON);
    assert_ok(&[b"--json", b"--", B], BASIC_JSON);
    assert_ok(&[B, b"--"], BASIC_ALL);
    assert_ok(&[B, b"--top", b"999999999999999999"], BASIC_ALL);
    assert_ok(&[B, b"--top", b"1000000000000000000"], BASIC_ALL);
    assert_ok(&[B, b"--top", "9".repeat(5000).as_bytes()], BASIC_ALL);
}

#[test]
fn r4_positional_lookalikes() {
    assert_input_error(&[b"--", b"-x"], "wordfreq: error: file not found: -x\n");
    assert_input_error(&[b"--", b"--"], "wordfreq: error: file not found: --\n");
    assert_input_error(&[b"-5"], "wordfreq: error: file not found: -5\n");
    assert_input_error(&[b"-1.5"], "wordfreq: error: file not found: -1.5\n");
    assert_input_error(&[b"-.5"], "wordfreq: error: file not found: -.5\n");
    assert_input_error(
        &["-\u{663}".as_bytes()],
        "wordfreq: error: file not found: -\u{663}\n",
    );
    assert_input_error(&[b"-5\n"], "wordfreq: error: file not found: -5\n\n");
    assert_input_error(&[b"- x"], "wordfreq: error: file not found: - x\n");
    assert_input_error(
        &[b"--foo bar"],
        "wordfreq: error: file not found: --foo bar\n",
    );
}

#[test]
fn r4_usage_errors() {
    for args in [
        &[B, b"--top="][..],
        &[B, b"--top", b"0", b"--top", b"2"],
        &[B, b"--top", b"2", b"--top", b"0"],
        &[B, b"tests/fixtures/ties.txt"],
        &[B, b"--json=1"],
        &[B, b"--json="],
        &[B, b"--top"],
        &[B, b"--top", b"--json"],
        &[B, b"--top", b"--", b"2"],
        &[B, b"--top", b"-1"],
        &[B, b"--top", b" 3"],
        &[B, b"--top", b"3 "],
        &[B, b"--top", b""],
        &[B, b"--top", b"000"],
        &[B, b"--top", "\u{663}".as_bytes()],
        &[b"--"],
        &[b"--", B, b"--json"],
        &[B, b"--json", b"--"],
        &[B, b"--", b"--"],
        &[b"-5\n\n"],
        &[b"-5x"],
        &[B, b"-5"],
        &[b"-x.txt"],
        &[B, b"---"],
        &[B, b"--=x"],
        &[b"-h-x"],
        &[b"-h=x"],
        &[b"--help=x"],
        &[B, b"--top", b"0", b"-h"],
        &[],
    ] {
        assert_usage(args);
    }
}

#[test]
fn r4_help_exits_zero() {
    for args in [
        &[b"-h".as_slice()][..],
        &[b"--help"],
        &[b"--he"],
        &[b"-hh"],
        &[b"-hfoo"],
        &[B, b"-h"],
        &[b"--bogus", b"-h"],
        &[b"-h", B, b"--top", b"0"],
    ] {
        let out = run(args);
        assert_eq!(out.status.code(), Some(0), "{args:?}");
        assert!(
            out.stdout
                .starts_with(b"usage: wordfreq [-h] [--top TOP] [--json] file\n"),
            "{args:?}"
        );
        assert!(out.stderr.is_empty(), "{args:?}");
    }
}

#[test]
fn r5_pathlib_normalization() {
    assert_ok(&[b"tests/fixtures/basic.txt/"], BASIC_ALL);
    assert_ok(&[b"tests/fixtures/basic.txt/."], BASIC_ALL);
    assert_ok(&[b"tests/fixtures/./basic.txt"], BASIC_ALL);
    assert_ok(&[b"./tests//fixtures/basic.txt"], BASIC_ALL);
    assert_ok(&[b"tests/fixtures/../fixtures/basic.txt"], BASIC_ALL);
    assert_input_error(&[b""], "wordfreq: error: cannot read file: \n");
    assert_input_error(&[b"."], "wordfreq: error: cannot read file: .\n");
    assert_input_error(
        &[b"tests/fixtures/"],
        "wordfreq: error: cannot read file: tests/fixtures/\n",
    );
    assert_input_error(
        &[b"nope.txt/"],
        "wordfreq: error: file not found: nope.txt/\n",
    );
}

#[test]
fn r7_read_errors() {
    assert_input_error(
        &[b"tests/fixtures/basic.txt/x"],
        "wordfreq: error: cannot read file: tests/fixtures/basic.txt/x\n",
    );
    let long = "a".repeat(300);
    assert_input_error(
        &[long.as_bytes()],
        &format!("wordfreq: error: cannot read file: {long}\n"),
    );
    assert_input_error(
        &[b"tests/fixtures/invalid_utf8.txt"],
        "wordfreq: error: not valid UTF-8: tests/fixtures/invalid_utf8.txt\n",
    );
    assert_input_error(
        &[b"gone\xff.txt"],
        "wordfreq: error: file not found: gone\u{fffd}.txt\n",
    );
}

#[test]
fn r12_non_utf8_option_values_follow_contract() {
    // 기준 구현은 UnicodeEncodeError 로 1 을 내지만 계약 4절은 인자 오류 2 를 요구한다
    assert_usage(&[B, b"--top", b"\xff"]);
    assert_usage(&[B, b"--\xff"]);
    assert_usage(&[B, b"\xff"]);
    assert_usage(&[B, b"--top=\xff"]);
}

#[cfg(target_os = "linux")]
#[test]
fn r9_disk_full_is_an_error() {
    let full = std::fs::OpenOptions::new()
        .write(true)
        .open("/dev/full")
        .expect("open /dev/full");
    let out = Command::new(env!("CARGO_BIN_EXE_wordfreq"))
        .arg("tests/fixtures/basic.txt")
        .current_dir(root())
        .stdout(Stdio::from(full))
        .stderr(Stdio::piped())
        .output()
        .expect("run wordfreq");
    assert_eq!(out.status.code(), Some(1));
    assert_eq!(
        String::from_utf8_lossy(&out.stderr),
        "wordfreq: error: cannot write output\n"
    );
}

#[cfg(target_os = "linux")]
#[test]
fn d1_help_write_failure_is_nonzero() {
    for args in [
        &["-h"][..],
        &["--help"][..],
        &["tests/fixtures/basic.txt", "-h"][..],
    ] {
        let full = std::fs::OpenOptions::new()
            .write(true)
            .open("/dev/full")
            .expect("open /dev/full");
        let out = Command::new(env!("CARGO_BIN_EXE_wordfreq"))
            .args(args)
            .current_dir(root())
            .stdout(Stdio::from(full))
            .stderr(Stdio::piped())
            .output()
            .expect("run wordfreq");
        assert_eq!(out.status.code(), Some(120), "args {args:?}");
    }
}
