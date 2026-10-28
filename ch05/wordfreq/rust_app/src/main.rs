//! wordfreq 명령행 진입점: 인자 해석, 파일 읽기, 출력, 종료 코드 (계약 3·4절).

use std::env;
use std::fs;
use std::io::{self, ErrorKind, Write};
use std::process::ExitCode;

use wordfreq::{Command, USAGE, count_words, format_json, format_text, parse_args, tokenize};

const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2;

fn main() -> ExitCode {
    let options = match parse_args(env::args_os().skip(1)) {
        Ok(Command::Run(options)) => options,
        Ok(Command::Help) => {
            println!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        Err(message) => {
            eprintln!("{USAGE}");
            eprintln!("wordfreq: error: {message}");
            return ExitCode::from(EXIT_USAGE_ERROR);
        }
    };

    // 오류 메시지의 <FILE>은 사용자가 입력한 문자열 그대로다 (계약 4절).
    let shown = options.file.to_string_lossy();
    let bytes = match fs::read(&options.file) {
        Ok(bytes) => bytes,
        Err(err) if err.kind() == ErrorKind::NotFound => {
            eprintln!("wordfreq: error: file not found: {shown}");
            return ExitCode::from(EXIT_INPUT_ERROR);
        }
        Err(_) => {
            // 디렉터리, 권한 없음 등
            eprintln!("wordfreq: error: cannot read file: {shown}");
            return ExitCode::from(EXIT_INPUT_ERROR);
        }
    };
    let Ok(text) = String::from_utf8(bytes) else {
        eprintln!("wordfreq: error: not valid UTF-8: {shown}");
        return ExitCode::from(EXIT_INPUT_ERROR);
    };

    let report = count_words(&tokenize(&text), options.top);
    let output = if options.json {
        format_json(&report)
    } else {
        format_text(&report)
    };
    // 운영체제와 무관하게 UTF-8 바이트와 LF를 그대로 쓴다.
    let mut stdout = io::stdout().lock();
    if stdout
        .write_all(output.as_bytes())
        .and_then(|()| stdout.flush())
        .is_err()
    {
        return ExitCode::FAILURE;
    }
    ExitCode::SUCCESS
}
