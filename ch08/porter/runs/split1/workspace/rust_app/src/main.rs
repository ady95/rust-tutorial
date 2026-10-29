//! wordfreq: 텍스트 파일의 단어 빈도를 센다 (python_src/wordfreq.py 2판의 Rust 이식).
//!
//! 동작 계약: contracts/behavior_spec.md
//! 출력은 모두 write_all + flush 결과를 확인한다. print!/println!/eprintln! 은 쓰지 않는다
//! (쓰기 실패 시 panic 하기 때문).

mod cli;
mod output;
mod text;

use std::ffi::OsString;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

const EXIT_OK: u8 = 0;
const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2;
const EXIT_OUTPUT_ERROR: u8 = 1;
/// 도움말을 stdout 에 쓰지 못했을 때 (Python 인터프리터 종료 시 flush 실패 코드와 같음)
const EXIT_HELP_WRITE_ERROR: u8 = 120;

/// stderr 에 쓴다. 실패는 무시한다 (stderr 가 닫혀 있어도 panic 하지 않음)
fn write_stderr(message: &str) {
    let mut err = io::stderr().lock();
    let _ = err.write_all(message.as_bytes());
    let _ = err.flush();
}

/// stdout 에 쓴다. 실패하면 false (계약 5절)
fn write_stdout(text: &str) -> bool {
    let mut out = io::stdout().lock();
    out.write_all(text.as_bytes()).is_ok() && out.flush().is_ok()
}

/// pathlib.Path(arg) 의 정규화를 흉내 낸다: 빈 성분·'.' 성분·끝의 '/' 를 없애고, 비면 '.'.
/// (Rust 는 맨 앞의 '.' 을 남기고 '//' 를 '/' 로 줄이지만 Linux 에서 여는 대상은 같다)
fn normalize(arg: &OsString) -> PathBuf {
    let path: PathBuf = Path::new(arg).components().collect();
    if path.as_os_str().is_empty() {
        PathBuf::from(".")
    } else {
        path
    }
}

enum ReadError {
    NotFound,
    NotUtf8,
    Other,
}

fn read_text(arg: &OsString) -> Result<String, ReadError> {
    let bytes = std::fs::read(normalize(arg)).map_err(|err| match err.kind() {
        io::ErrorKind::NotFound => ReadError::NotFound,
        _ => ReadError::Other,
    })?;
    String::from_utf8(bytes).map_err(|_| ReadError::NotUtf8)
}

fn run() -> u8 {
    let args: Vec<OsString> = std::env::args_os().skip(1).collect();
    let args = match cli::parse(&args) {
        cli::Outcome::Run(args) => args,
        cli::Outcome::Help => {
            // 도움말 쓰기(write_all+flush)가 실패하면 기준 구현처럼 120 으로 끝낸다
            // (Python 은 종료 시 stdout flush 실패로 120. 계약 5절: 0 이 아니어야 함)
            if !write_stdout(cli::HELP) {
                return EXIT_HELP_WRITE_ERROR;
            }
            return EXIT_OK;
        }
        cli::Outcome::Usage(message) => {
            write_stderr(&format!("{}wordfreq: error: {message}\n", cli::USAGE));
            return EXIT_USAGE_ERROR;
        }
    };

    let name = cli::display_name(&args.file);
    let text = match read_text(&args.file) {
        Ok(text) => text,
        Err(ReadError::NotFound) => {
            write_stderr(&format!("wordfreq: error: file not found: {name}\n"));
            return EXIT_INPUT_ERROR;
        }
        Err(ReadError::NotUtf8) => {
            write_stderr(&format!("wordfreq: error: not valid UTF-8: {name}\n"));
            return EXIT_INPUT_ERROR;
        }
        Err(ReadError::Other) => {
            write_stderr(&format!("wordfreq: error: cannot read file: {name}\n"));
            return EXIT_INPUT_ERROR;
        }
    };

    let words = text::tokenize(&text);
    let report = text::count_words(&words, args.top);
    let rendered = if args.json {
        output::format_json(&report)
    } else {
        output::format_text(&report)
    };
    if !write_stdout(&rendered) {
        write_stderr("wordfreq: error: cannot write output\n");
        return EXIT_OUTPUT_ERROR;
    }
    EXIT_OK
}

fn main() -> ExitCode {
    ExitCode::from(run())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn r5_normalize_like_pathlib() {
        // 기대값: Python str(pathlib.Path(x)) (verify/probe_text.py 출력)
        let cases = [
            ("", "."),
            (".", "."),
            ("tests/fixtures/basic.txt/", "tests/fixtures/basic.txt"),
            ("tests/fixtures/basic.txt/.", "tests/fixtures/basic.txt"),
            ("tests/fixtures/./basic.txt", "tests/fixtures/basic.txt"),
            ("a//b", "a/b"),
            ("a/../b", "a/../b"),
        ];
        for (input, expected) in cases {
            assert_eq!(
                normalize(&OsString::from(input)),
                PathBuf::from(expected),
                "{input:?}"
            );
        }
        // pathlib 은 './a' 를 'a' 로 줄이고 Rust 는 './a' 로 남기지만 가리키는 파일은 같다
        assert_eq!(normalize(&OsString::from("./a")), PathBuf::from("./a"));
    }
}
