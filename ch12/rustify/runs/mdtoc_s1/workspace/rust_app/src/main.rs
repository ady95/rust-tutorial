//! mdtoc: Markdown 제목으로 목차를 만든다. python_src/mdtoc.py 의 Rust 구현(std 만 사용).

mod cli;
mod headings;
mod pystr;
mod render;
mod slug;
#[rustfmt::skip]
mod unicode_tables;

use std::ffi::OsStr;
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::unix::ffi::{OsStrExt, OsStringExt};

/// 파일 이름을 stderr 에 쓸 문자열로. UTF-8 이 아닌 바이트는 Python 의 backslashreplace 처럼 `\udcXX`.
fn display_name(bytes: &[u8]) -> String {
    let mut out = String::new();
    let mut rest = bytes;
    loop {
        match std::str::from_utf8(rest) {
            Ok(s) => {
                out.push_str(s);
                return out;
            }
            Err(e) => {
                let (valid, bad) = rest.split_at(e.valid_up_to());
                out.push_str(&String::from_utf8_lossy(valid));
                let len = e.error_len().unwrap_or(bad.len());
                for b in &bad[..len] {
                    out.push_str(&format!("\\udc{b:02x}"));
                }
                rest = &bad[len..];
            }
        }
    }
}

/// `io::Error` 의 Display 에서 ` (os error N)` 을 뗀 strerror 문구.
fn strerror(err: &io::Error) -> String {
    let text = err.to_string();
    match text.rfind(" (os error ") {
        Some(i) => text[..i].to_string(),
        None => text,
    }
}

fn read_input(file: &[u8]) -> io::Result<Vec<u8>> {
    let mut data = Vec::new();
    if file == b"-" {
        io::stdin().lock().read_to_end(&mut data)?;
    } else {
        File::open(OsStr::from_bytes(file))?.read_to_end(&mut data)?;
    }
    Ok(data)
}

fn write_stdout(text: &str) {
    let _ = io::stdout().lock().write_all(text.as_bytes());
}

fn fail(message: &str) -> i32 {
    let _ = io::stderr().lock().write_all(message.as_bytes());
    1
}

fn run() -> i32 {
    let args: Vec<Vec<u8>> = std::env::args_os().skip(1).map(|a| a.into_vec()).collect();
    let opts = match cli::parse(&args) {
        cli::Parsed::Help => {
            write_stdout(cli::HELP);
            return 0;
        }
        cli::Parsed::Usage(message) => {
            let _ = io::stderr()
                .lock()
                .write_all(format!("{}\nmdtoc: error: {message}\n", cli::USAGE).as_bytes());
            return 2;
        }
        cli::Parsed::Run(opts) => opts,
    };
    let name = if opts.file == b"-" {
        "<stdin>".to_string()
    } else {
        display_name(&opts.file)
    };
    let data = match read_input(&opts.file) {
        Ok(data) => data,
        Err(err) => {
            return fail(&format!(
                "mdtoc: error: cannot read {name}: {}\n",
                strerror(&err)
            ))
        }
    };
    let Ok(text) = std::str::from_utf8(&data) else {
        return fail(&format!("mdtoc: error: {name}: not valid UTF-8\n"));
    };
    let entries = slug::build(text, opts.min_level, opts.max_level);
    if opts.json {
        write_stdout(&render::render_json(&entries));
    } else {
        write_stdout(&render::render(&entries, opts.min_level));
    }
    0
}

fn main() {
    std::process::exit(run());
}
