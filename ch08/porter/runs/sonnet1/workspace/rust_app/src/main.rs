mod cli;
mod output;
mod py_tables;
mod text;

use std::io::Write;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;

const EXIT_INPUT_ERROR: u8 = 1;
const EXIT_USAGE_ERROR: u8 = 2;
const EXIT_OUTPUT_ERROR: u8 = 1;

/// stderr 쓰기 실패는 무시한다 (eprintln! 은 실패하면 panic 한다)
fn write_stderr(message: &str) {
    let _ = std::io::stderr().write_all(message.as_bytes());
}

/// pathlib.Path 처럼 끝의 `/` 와 `.` 조각을 없앤다. 비면 `.`
fn normalize(path: &Path) -> PathBuf {
    let normalized: PathBuf = path
        .components()
        .filter(|c| !matches!(c, Component::CurDir))
        .collect();
    if normalized.as_os_str().is_empty() {
        PathBuf::from(".")
    } else {
        normalized
    }
}

fn read_input(file: &std::ffi::OsStr) -> Result<String, &'static str> {
    let bytes = std::fs::read(normalize(Path::new(file))).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            "file not found"
        } else {
            "cannot read file"
        }
    })?;
    String::from_utf8(bytes).map_err(|_| "not valid UTF-8")
}

fn main() -> ExitCode {
    let args = match cli::parse(std::env::args_os().skip(1)) {
        cli::Parsed::Run(args) => args,
        cli::Parsed::Help => {
            let ok = std::io::stdout().write_all(cli::HELP.as_bytes()).is_ok();
            return ExitCode::from(if ok { 0 } else { EXIT_OUTPUT_ERROR });
        }
        cli::Parsed::Usage(message) => {
            write_stderr(&format!("{}wordfreq: error: {message}\n", cli::USAGE));
            return ExitCode::from(EXIT_USAGE_ERROR);
        }
    };

    let text = match read_input(&args.file) {
        Ok(text) => text,
        Err(reason) => {
            let name = cli::display_name(&args.file);
            write_stderr(&format!("wordfreq: error: {reason}: {name}\n"));
            return ExitCode::from(EXIT_INPUT_ERROR);
        }
    };

    let report = text::count_words(&text::tokenize(&text), args.top);
    let rendered = if args.json {
        output::format_json(&report)
    } else {
        output::format_text(&report)
    };
    let mut stdout = std::io::stdout().lock();
    if stdout.write_all(rendered.as_bytes()).is_err() || stdout.flush().is_err() {
        write_stderr("wordfreq: error: cannot write output\n");
        return ExitCode::from(EXIT_OUTPUT_ERROR);
    }
    ExitCode::SUCCESS
}
