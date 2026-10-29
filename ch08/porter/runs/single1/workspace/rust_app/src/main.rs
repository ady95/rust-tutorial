//! wordfreq: 텍스트 파일의 단어 빈도를 세는 CLI (python_src/wordfreq.py 기준 구현 2판의 Rust 이식).
//!
//! 동작 계약은 contracts/behavior_spec.md 에 있다.

mod cli;
mod output;
mod text;

use std::ffi::OsString;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use cli::Outcome;

const EXIT_OK: u8 = 0;
const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2; // argparse 가 쓰는 값과 같다
const EXIT_OUTPUT_ERROR: u8 = 1;

/// stderr 에 한 줄 쓴다. stderr 가 닫혀 있어도 멈추지 않도록 결과는 무시한다 (eprintln! 은 panic 한다)
fn print_err(message: &str) {
    let _ = io::stderr().lock().write_all(message.as_bytes());
}

/// stdout 에 쓴다. 파이프가 닫혔거나 디스크가 가득 차면 false (계약 5절)
fn write_output(text: &str) -> bool {
    let mut out = io::stdout().lock();
    out.write_all(text.as_bytes())
        .and_then(|()| out.flush())
        .is_ok()
}

/// pathlib.Path 와 같게 경로를 정리한다: 끝의 '/' 와 중간·끝의 '.' 를 지우고, 빈 경로는 '.'
fn normalize(arg: &OsString) -> PathBuf {
    let path: PathBuf = Path::new(arg).components().collect();
    if path.as_os_str().is_empty() {
        PathBuf::from(".")
    } else {
        path
    }
}

fn run(args: cli::Args) -> u8 {
    let name = cli::display_name(&args.file);
    // fs::read_to_string 은 UTF-8 오류를 다른 io 오류와 같은 종류로 돌려주므로, 읽기와 디코딩을 나눈다
    let bytes = match std::fs::read(normalize(&args.file)) {
        Ok(bytes) => bytes,
        Err(err) if err.kind() == io::ErrorKind::NotFound => {
            print_err(&format!("wordfreq: error: file not found: {name}\n"));
            return EXIT_INPUT_ERROR;
        }
        Err(_) => {
            // 디렉터리, 권한 없음 등
            print_err(&format!("wordfreq: error: cannot read file: {name}\n"));
            return EXIT_INPUT_ERROR;
        }
    };
    let Ok(content) = String::from_utf8(bytes) else {
        print_err(&format!("wordfreq: error: not valid UTF-8: {name}\n"));
        return EXIT_INPUT_ERROR;
    };

    let report = text::count_words(text::tokenize(&content), args.top);
    let rendered = if args.json {
        output::format_json(&report)
    } else {
        output::format_text(&report)
    };
    if !write_output(&rendered) {
        print_err("wordfreq: error: cannot write output\n");
        return EXIT_OUTPUT_ERROR;
    }
    EXIT_OK
}

fn main() -> ExitCode {
    // args() 는 UTF-8 이 아닌 인자에서 panic 하므로 args_os() 를 쓴다
    let argv: Vec<OsString> = std::env::args_os().skip(1).collect();
    let code = match cli::parse(&argv) {
        Outcome::Run(args) => run(args),
        Outcome::Help => {
            // argparse 는 도움말 쓰기 실패(OSError)를 무시하고 0 으로 끝낸다
            let _ = write_output(cli::HELP);
            EXIT_OK
        }
        Outcome::Usage(message) => {
            print_err(&format!("{}wordfreq: error: {message}\n", cli::USAGE));
            EXIT_USAGE_ERROR
        }
    };
    ExitCode::from(code)
}
