//! wordfreq: 텍스트 파일의 단어 빈도를 세는 CLI (04장 Rust 구현).
//!
//! 동작 계약은 contracts/behavior_spec.md, 기준 구현은 python_src/wordfreq.py 이다.

mod cli;
mod pystr;
mod report;

use std::env;
use std::ffi::{OsStr, OsString};
use std::fs::File;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

const EXIT_OK: u8 = 0;
const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2; // argparse 가 쓰는 값과 같다
/// Python 은 종료 직전 stdout 을 비우다 실패하면(파이프가 닫힘 등) 120 으로 끝난다.
const EXIT_FLUSH_ERROR: u8 = 120;

enum ReadError {
    NotFound,
    NotUtf8,
    Other,
}

fn main() -> ExitCode {
    let argv: Vec<OsString> = env::args_os().skip(1).collect();
    ExitCode::from(run(&argv, &mut io::stdout().lock(), &mut io::stderr().lock()))
}

/// 기준 구현의 `main(argv)`. 종료 코드를 돌려준다.
/// 출력은 운영체제와 무관하게 UTF-8, 줄바꿈은 LF 다 (계약 3절). Rust 문자열을 바이트 그대로 쓰면 된다.
fn run(argv: &[OsString], stdout: &mut impl Write, stderr: &mut impl Write) -> u8 {
    let args = match cli::parse(argv) {
        cli::Parsed::Run(args) => args,
        cli::Parsed::Help => return write_stdout(stdout, cli::HELP),
        cli::Parsed::Error(message) => {
            let _ = writeln!(stderr, "{}wordfreq: error: {message}", cli::USAGE);
            return EXIT_USAGE_ERROR;
        }
    };

    let text = match read_text(&args.file) {
        Ok(text) => text,
        Err(err) => {
            let reason = match err {
                ReadError::NotFound => "file not found",
                ReadError::NotUtf8 => "not valid UTF-8",
                ReadError::Other => "cannot read file", // 디렉터리, 권한 없음 등
            };
            let _ = writeln!(stderr, "wordfreq: error: {reason}: {}", args.file.to_string_lossy());
            return EXIT_INPUT_ERROR;
        }
    };

    let report = report::count_words(report::tokenize(&text), args.top);
    write_stdout(stdout, &if args.json { report::format_json(&report) } else { report::format_text(&report) })
}

fn read_text(file: &OsStr) -> Result<String, ReadError> {
    let mut handle = File::open(like_pathlib(file)).map_err(|err| {
        if is_not_found(&err) { ReadError::NotFound } else { ReadError::Other }
    })?;
    let mut bytes = Vec::new();
    handle.read_to_end(&mut bytes).map_err(|_| ReadError::Other)?;
    String::from_utf8(bytes).map_err(|_| ReadError::NotUtf8)
}

/// 기준 구현은 `Path(FILE)` 를 연다. pathlib 은 빈 문자열을 "." 로 바꾸고,
/// 끝의 구분자와 가운데의 "." 조각을 없앤다 ("a.txt/" 도 a.txt 로 열린다).
fn like_pathlib(file: &OsStr) -> PathBuf {
    let path: PathBuf = Path::new(file).components().collect();
    if path.as_os_str().is_empty() { PathBuf::from(".") } else { path }
}

/// Python 은 Windows 에서 MSVC CRT 의 `_wopen` 으로 파일을 열고, errno 가 ENOENT 일 때
/// FileNotFoundError 를 낸다. CRT 가 ENOENT 로 바꾸는 Win32 오류 코드를 그대로 쓴다.
#[cfg(windows)]
fn is_not_found(err: &io::Error) -> bool {
    // FILE_NOT_FOUND, PATH_NOT_FOUND, INVALID_DRIVE, NO_MORE_FILES,
    // BAD_NETPATH, BAD_NET_NAME, BAD_PATHNAME, FILENAME_EXCED_RANGE
    matches!(err.raw_os_error(), Some(2 | 3 | 15 | 18 | 53 | 67 | 161 | 206))
}

#[cfg(not(windows))]
fn is_not_found(err: &io::Error) -> bool {
    err.kind() == io::ErrorKind::NotFound
}

fn write_stdout(stdout: &mut impl Write, text: &str) -> u8 {
    match stdout.write_all(text.as_bytes()).and_then(|()| stdout.flush()) {
        Ok(()) => EXIT_OK,
        Err(_) => EXIT_FLUSH_ERROR,
    }
}

#[cfg(test)]
mod tests {
    //! tests/cases.json 의 케이스를 프로세스 안에서 돌린다 (실행 파일을 띄우는 판은 tests/cli.rs).
    //! cargo test 는 rust_app/ 에서 실행되므로 픽스처 경로에 ../ 가 붙는다.

    use super::*;

    fn wordfreq(args: &[&str]) -> (u8, String, String) {
        let argv: Vec<OsString> = args.iter().map(OsString::from).collect();
        let (mut out, mut err) = (Vec::new(), Vec::new());
        let code = run(&argv, &mut out, &mut err);
        (code, String::from_utf8(out).unwrap(), String::from_utf8(err).unwrap())
    }

    fn assert_ok(args: &[&str], stdout: &str) {
        assert_eq!(wordfreq(args), (EXIT_OK, stdout.to_string(), String::new()), "{args:?}");
    }

    fn assert_input_error(args: &[&str], stderr: &str) {
        assert_eq!(wordfreq(args), (EXIT_INPUT_ERROR, String::new(), stderr.to_string()), "{args:?}");
    }

    fn assert_usage_error(args: &[&str]) {
        let (code, out, err) = wordfreq(args);
        assert_eq!((code, out.as_str()), (EXIT_USAGE_ERROR, ""), "{args:?}");
        assert!(!err.is_empty(), "{args:?}");
    }

    const BASIC: &str = "words: 10\nunique: 6\n3\trust\n2\tis\n2\tpython\n1\tand\n1\tfast\n1\tfriendly\n";

    #[test]
    fn basic() {
        assert_ok(&["../tests/fixtures/basic.txt"], BASIC);
        assert_ok(&["../tests/fixtures/basic.txt", "--top", "2"], "words: 10\nunique: 6\n3\trust\n2\tis\n");
        assert_ok(
            &["../tests/fixtures/basic.txt", "--json"],
            "{\"words\":10,\"unique\":6,\"top\":[{\"word\":\"rust\",\"count\":3},{\"word\":\"is\",\"count\":2},\
             {\"word\":\"python\",\"count\":2},{\"word\":\"and\",\"count\":1},{\"word\":\"fast\",\"count\":1},\
             {\"word\":\"friendly\",\"count\":1}]}\n",
        );
    }

    #[test]
    fn korean() {
        assert_ok(
            &["../tests/fixtures/korean.txt"],
            "words: 12\nunique: 11\n2\t러스트는\n1\tpython\n1\trust와\n1\t러스트로\n1\t만들고\n\
             1\t빠르다\n1\t쉽다\n1\t옮긴다\n1\t컴파일한다\n1\t파이썬으로\n",
        );
        assert_ok(
            &["../tests/fixtures/korean.txt", "--json", "--top", "3"],
            "{\"words\":12,\"unique\":11,\"top\":[\
             {\"word\":\"러스트는\",\"count\":2},{\"word\":\"python\",\"count\":1},{\"word\":\"rust와\",\"count\":1}]}\n",
        );
    }

    #[test]
    fn punctuation_ties_crlf() {
        assert_ok(
            &["../tests/fixtures/punctuation.txt", "--top", "20"],
            "words: 12\nunique: 12\n1\tdon't\n1\tdot\n1\te-mail\n1\thello\n1\tme\n1\tplease\n\
             1\tquoted\n1\tsaid\n1\tshe\n1\tsingle\n1\tstop\n1\twait\n",
        );
        assert_ok(&["../tests/fixtures/ties.txt"], "words: 7\nunique: 4\n2\ta\n2\tb\n2\tc\n1\td\n");
        assert_ok(
            &["../tests/fixtures/crlf_case.txt", "--json"],
            "{\"words\":6,\"unique\":4,\"top\":[{\"word\":\"upper\",\"count\":3},\
             {\"word\":\"endings\",\"count\":1},{\"word\":\"line\",\"count\":1},{\"word\":\"windows\",\"count\":1}]}\n",
        );
    }

    #[test]
    fn empty() {
        assert_ok(&["../tests/fixtures/empty.txt"], "words: 0\nunique: 0\n");
        assert_ok(&["../tests/fixtures/empty.txt", "--json"], "{\"words\":0,\"unique\":0,\"top\":[]}\n");
    }

    #[test]
    fn input_errors() {
        assert_input_error(
            &["../tests/fixtures/no_such_file.txt"],
            "wordfreq: error: file not found: ../tests/fixtures/no_such_file.txt\n",
        );
        assert_input_error(
            &["../tests/fixtures/invalid_utf8.txt"],
            "wordfreq: error: not valid UTF-8: ../tests/fixtures/invalid_utf8.txt\n",
        );
        assert_input_error(&["../tests/fixtures"], "wordfreq: error: cannot read file: ../tests/fixtures\n");
        assert_input_error(
            &["../tests/fixtures/basic.txt/x"],
            if cfg!(windows) {
                "wordfreq: error: file not found: ../tests/fixtures/basic.txt/x\n"
            } else {
                "wordfreq: error: cannot read file: ../tests/fixtures/basic.txt/x\n"
            },
        );
    }

    #[test]
    fn usage_errors() {
        assert_usage_error(&[]);
        assert_usage_error(&["../tests/fixtures/basic.txt", "--top", "0"]);
        assert_usage_error(&["../tests/fixtures/basic.txt", "--top", "abc"]);
        assert_usage_error(&["../tests/fixtures/basic.txt", "--bogus"]);
    }

    #[test]
    fn paths_are_opened_like_pathlib() {
        // Path("") 는 "." (디렉터리), Path("a.txt/") 는 a.txt 이다.
        assert_input_error(&[""], "wordfreq: error: cannot read file: \n");
        assert_ok(&["../tests/fixtures/basic.txt/"], BASIC);
        assert_ok(&["../tests/./fixtures//basic.txt"], BASIC);
    }

    #[test]
    fn help_goes_to_stdout() {
        assert_eq!(wordfreq(&["-h"]), (EXIT_OK, cli::HELP.to_string(), String::new()));
    }
}
