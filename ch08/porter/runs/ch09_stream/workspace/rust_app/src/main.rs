//! logstat 실행 파일: 인자 → 형식 추론 → 파일 읽기 → UTF-8 해석 → run → 출력.

use std::borrow::Cow;
use std::ffi::{OsStr, OsString};
use std::io::{ErrorKind, Write};

use logstat::cli::{self, Outcome, USAGE};
use logstat::help;
use logstat::{run, Format, EXIT_INPUT_ERROR, EXIT_OK, EXIT_USAGE_ERROR};

#[cfg(unix)]
fn os_bytes(s: &OsStr) -> Cow<'_, [u8]> {
    use std::os::unix::ffi::OsStrExt;
    Cow::Borrowed(s.as_bytes())
}

#[cfg(not(unix))]
fn os_bytes(s: &OsStr) -> Cow<'_, [u8]> {
    Cow::Owned(s.to_string_lossy().into_owned().into_bytes())
}

/// `file.lower().endswith(...)`. 이 접미사 글자로 소문자화되는 비ASCII 글자는 없다(verify/probe.py).
fn infer_format(file: &OsStr) -> Option<Format> {
    let lower = os_bytes(file).to_ascii_lowercase();
    if lower.ends_with(b".csv") {
        Some(Format::Csv)
    } else if lower.ends_with(b".jsonl") || lower.ends_with(b".ndjson") {
        Some(Format::Jsonl)
    } else {
        None
    }
}

fn usage_error(msg: &str) -> i32 {
    eprintln!("{USAGE}logstat: error: {msg}");
    EXIT_USAGE_ERROR
}

fn input_error(what: &str, file: &OsStr) -> i32 {
    eprintln!("logstat: error: {what}: {}", file.to_string_lossy());
    EXIT_INPUT_ERROR
}

fn real_main(argv: &[OsString]) -> i32 {
    let args = match cli::parse(argv) {
        Outcome::Help => {
            let text = help::help_text(help::columns());
            let _ = std::io::stdout().write_all(text.as_bytes());
            return EXIT_OK;
        }
        Outcome::Error(msg) => return usage_error(&msg),
        Outcome::Run(args) => args,
    };
    let Some(fmt) = args.format.or_else(|| infer_format(&args.file)) else {
        return usage_error("cannot infer --format from the file name");
    };
    let data = match std::fs::read(&args.file) {
        Ok(data) => data,
        Err(e) if e.kind() == ErrorKind::NotFound => {
            return input_error("file not found", &args.file)
        }
        Err(_) => return input_error("cannot read file", &args.file),
    };
    let Ok(text) = std::str::from_utf8(&data) else {
        return input_error("not valid UTF-8", &args.file);
    };
    let (code, out, err) = run(text, fmt, args.top, args.json, args.strict);
    if std::str::from_utf8(&out).is_err() {
        // JSON 의 짝 없는 서로게이트(\ud800 등)가 든 경로가 출력에 들어갔다.
        // Python 은 sys.stdout.write 에서 UnicodeEncodeError 로 끝나므로(stdout 비어 있음, 종료 1) 그것을 흉내 낸다.
        eprintln!(
            "UnicodeEncodeError: 'utf-8' codec can't encode characters: surrogates not allowed"
        );
        return EXIT_INPUT_ERROR;
    }
    let _ = std::io::stdout().write_all(&out);
    let _ = std::io::stderr().write_all(&err);
    code
}

fn main() {
    let argv: Vec<OsString> = std::env::args_os().skip(1).collect();
    let code = real_main(&argv);
    let _ = std::io::stdout().flush();
    std::process::exit(code);
}
