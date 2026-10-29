//! wordfreq: 텍스트 파일의 단어 빈도를 세는 CLI (python_src/wordfreq.py 2판의 Rust 이식).
//!
//! 동작 계약은 contracts/behavior_spec.md 에 있다.

mod cli;
mod output;
mod text;
mod unicode_tables;

use std::env;
use std::ffi::OsStr;
use std::fs;
use std::io::{self, ErrorKind, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use cli::{Args, Command};

const EXIT_OK: u8 = 0;
const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2; // argparse 가 쓰는 값과 같다
const EXIT_OUTPUT_ERROR: u8 = 1;

/// 오류 메시지에 넣을 파일 이름. UTF-8 이 아닌 바이트는 U+FFFD 로 바꾼다 (계약 4절).
fn display_name(arg: &OsStr) -> String {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        String::from_utf8_lossy(arg.as_bytes()).into_owned()
    }
    #[cfg(not(unix))]
    {
        arg.to_string_lossy().into_owned()
    }
}

/// pathlib.Path 처럼 경로를 정리한다 ('a/', 'a/.' 는 'a', '' 는 '.')
fn normalize(arg: &OsStr) -> PathBuf {
    let path: PathBuf = Path::new(arg).components().collect();
    if path.as_os_str().is_empty() {
        PathBuf::from(".")
    } else {
        path
    }
}

/// stderr 에 한 줄 쓴다. stderr 가 닫혀 있어도 멈추지 않도록 결과는 무시한다
fn print_error(message: &str) {
    let _ = io::stderr().write_all(format!("wordfreq: error: {message}\n").as_bytes());
}

/// stdout 에 쓴다. 파이프가 닫혔거나 디스크가 가득 차면 false (계약 5절).
fn write_output(text: &str) -> bool {
    let mut stdout = io::stdout().lock();
    stdout.write_all(text.as_bytes()).is_ok() && stdout.flush().is_ok()
}

fn run(args: &Args) -> u8 {
    let name = display_name(&args.file);
    let bytes = match fs::read(normalize(&args.file)) {
        Ok(bytes) => bytes,
        Err(err) if err.kind() == ErrorKind::NotFound => {
            print_error(&format!("file not found: {name}"));
            return EXIT_INPUT_ERROR;
        }
        Err(_) => {
            // 디렉터리, 권한 없음 등
            print_error(&format!("cannot read file: {name}"));
            return EXIT_INPUT_ERROR;
        }
    };
    let Ok(text) = String::from_utf8(bytes) else {
        print_error(&format!("not valid UTF-8: {name}"));
        return EXIT_INPUT_ERROR;
    };

    let report = text::count_words(&text::tokenize(&text), args.top);
    let out = if args.json {
        output::format_json(&report)
    } else {
        output::format_text(&report)
    };
    if !write_output(&out) {
        print_error("cannot write output");
        return EXIT_OUTPUT_ERROR;
    }
    EXIT_OK
}

fn main() -> ExitCode {
    let args: Vec<_> = env::args_os().skip(1).collect();
    let code = match cli::parse(&args) {
        Ok(Command::Run(args)) => run(&args),
        Ok(Command::Help) => {
            // argparse 처럼 도움말 쓰기 실패는 무시하고 0 으로 끝낸다
            let _ = write_output(cli::HELP);
            EXIT_OK
        }
        Err(cli::UsageError(message)) => {
            let _ = io::stderr().write_all(cli::USAGE.as_bytes());
            print_error(&message);
            EXIT_USAGE_ERROR
        }
    };
    ExitCode::from(code)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_like_pathlib() {
        assert_eq!(normalize(OsStr::new("")), PathBuf::from("."));
        assert_eq!(normalize(OsStr::new("a.txt/")), PathBuf::from("a.txt"));
        assert_eq!(normalize(OsStr::new("a.txt/.")), PathBuf::from("a.txt"));
        assert_eq!(normalize(OsStr::new("x//./y")), PathBuf::from("x/y"));
    }

    #[cfg(unix)]
    #[test]
    fn display_name_replaces_maximal_subparts() {
        use std::os::unix::ffi::OsStrExt;
        let name = OsStr::from_bytes(b"x\xe2\x82y\xf0\x9f.txt");
        assert_eq!(display_name(name), "x\u{fffd}y\u{fffd}.txt");
    }

    #[test]
    fn unicode_tables_come_from_python_3_12() {
        assert_eq!(unicode_tables::UNIDATA_VERSION, "15.0.0");
    }
}
