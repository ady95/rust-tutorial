//! `-h`/`--help` 도움말. argparse `HelpFormatter`(Python 3.12)를 이 파서의 인자 구성에 맞춰 옮겼다.
//!
//! 폭은 `shutil.get_terminal_size().columns - 2`: 환경 변수 `COLUMNS`(Python `int()` 규칙)가 양수면 그 값,
//! 아니면 stdout 이 터미널일 때 그 폭, 그것도 아니면 80.

use crate::cli::decimal_value;

const PROG: &str = "logstat";
const PREFIX: &str = "usage: ";
const DESCRIPTION: &str = "Summarize CSV or JSON Lines access logs.";
const OPT_PARTS: [&str; 5] = [
    "[-h]",
    "[--format {csv,jsonl}]",
    "[--top TOP]",
    "[--json]",
    "[--strict]",
];
const POS_PARTS: [&str; 1] = ["file"];
/// (호출 표기, 도움말)
type ActionHelp = (&'static str, Option<&'static str>);
/// (섹션 제목, 인자들)
const SECTIONS: [(&str, &[ActionHelp]); 2] = [
    ("positional arguments", &[("file", None)]),
    (
        "options",
        &[
            ("-h, --help", Some("show this help message and exit")),
            (
                "--format {csv,jsonl}",
                Some("default: from the file extension"),
            ),
            ("--top TOP", None),
            ("--json", None),
            ("--strict", Some("stop at the first bad record")),
        ],
    ),
];
/// 섹션 안 들여쓰기(2) + 가장 긴 호출 표기("--format {csv,jsonl}", 20자)
const ACTION_MAX_LENGTH: i64 = 22;
/// 폭을 이 값으로 묶는다(Python 은 임의 정밀도 정수지만 이보다 넓으면 결과가 같다)
const MAX_COLUMNS: i64 = 1 << 40;

/// `str.isspace()` 인 127 이상의 코드 포인트(verify/int_charsets.py)
fn is_unicode_space(c: char) -> bool {
    matches!(
        c,
        '\u{85}' | '\u{a0}' | '\u{1680}' | '\u{2000}'
            ..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}'
    )
}

/// Python `int(s)`(10진). ValueError 면 None. 값은 ±MAX_COLUMNS 로 포화한다.
pub fn python_int(s: &str) -> Option<i64> {
    // _PyUnicode_TransformDecimalAndSpaceToASCII: 127 미만은 그대로, 나머지는 공백→' ', 10진 숫자→ASCII
    let mut ascii = Vec::with_capacity(s.len());
    for c in s.chars() {
        if (c as u32) < 127 {
            ascii.push(c as u8);
        } else if is_unicode_space(c) {
            ascii.push(b' ');
        } else {
            ascii.push(b'0' + decimal_value(c)? as u8);
        }
    }
    let is_space = |b: &u8| matches!(b, b' ' | b'\t' | b'\n' | 0x0B | 0x0C | b'\r');
    let start = ascii.iter().position(|b| !is_space(b))?;
    let end = ascii.iter().rposition(|b| !is_space(b))? + 1;
    let mut body = &ascii[start..end];
    let negative = body.first() == Some(&b'-');
    if matches!(body.first(), Some(b'-' | b'+')) {
        body = &body[1..];
    }
    // 숫자 사이에만 밑줄 하나
    if body.first() == Some(&b'_')
        || body.last() == Some(&b'_')
        || body.windows(2).any(|w| w == b"__")
    {
        return None;
    }
    let digits: Vec<u8> = body.iter().copied().filter(|&b| b != b'_').collect();
    if digits.is_empty() || !digits.iter().all(u8::is_ascii_digit) || digits.len() > 4300 {
        return None;
    }
    let mut value: i64 = 0;
    for d in digits {
        value = (value * 10 + i64::from(d - b'0')).min(MAX_COLUMNS);
    }
    Some(if negative { -value } else { value })
}

#[cfg(all(
    target_os = "linux",
    not(any(
        target_arch = "powerpc",
        target_arch = "powerpc64",
        target_arch = "mips",
        target_arch = "mips64",
        target_arch = "sparc",
        target_arch = "sparc64"
    ))
))]
fn terminal_columns() -> Option<i64> {
    #[repr(C)]
    struct WinSize {
        ws_row: u16,
        ws_col: u16,
        ws_xpixel: u16,
        ws_ypixel: u16,
    }
    extern "C" {
        fn ioctl(fd: i32, request: std::ffi::c_ulong, ...) -> i32;
    }
    const TIOCGWINSZ: std::ffi::c_ulong = 0x5413;
    let mut ws = WinSize {
        ws_row: 0,
        ws_col: 0,
        ws_xpixel: 0,
        ws_ypixel: 0,
    };
    // SAFETY: fd 1 에 TIOCGWINSZ 를 묻고, 커널은 ws 크기만큼만 쓴다
    let rc = unsafe { ioctl(1, TIOCGWINSZ, &mut ws as *mut WinSize) };
    (rc == 0).then_some(i64::from(ws.ws_col))
}

#[cfg(not(all(
    target_os = "linux",
    not(any(
        target_arch = "powerpc",
        target_arch = "powerpc64",
        target_arch = "mips",
        target_arch = "mips64",
        target_arch = "sparc",
        target_arch = "sparc64"
    ))
)))]
fn terminal_columns() -> Option<i64> {
    None
}

/// `shutil.get_terminal_size().columns`
pub fn columns() -> i64 {
    let env = std::env::var_os("COLUMNS").and_then(|v| python_int(&v.to_string_lossy()));
    match env {
        Some(c) if c > 0 => c,
        _ => match terminal_columns() {
            Some(c) if c > 0 => c,
            _ => 80,
        },
    }
}

/// textwrap.wrap(text, width): 낱말이 모두 width(11 이상)보다 짧고 하이픈이 없으므로 탐욕적 줄바꿈과 같다
fn wrap(text: &str, width: i64) -> Vec<String> {
    let mut lines = Vec::new();
    let mut line = String::new();
    for word in text.split(' ') {
        if !line.is_empty() && (line.len() + 1 + word.len()) as i64 > width {
            lines.push(std::mem::take(&mut line));
        }
        if !line.is_empty() {
            line.push(' ');
        }
        line.push_str(word);
    }
    lines.push(line);
    lines
}

fn get_lines(parts: &[&str], indent: usize, prefix: bool, text_width: i64) -> Vec<String> {
    let pad = " ".repeat(indent);
    let mut lines = Vec::new();
    let mut line: Vec<&str> = Vec::new();
    let mut line_len = if prefix { PREFIX.len() } else { indent } as i64 - 1;
    for &part in parts {
        if line_len + 1 + part.len() as i64 > text_width && !line.is_empty() {
            lines.push(format!("{pad}{}", line.join(" ")));
            line.clear();
            line_len = indent as i64 - 1;
        }
        line.push(part);
        line_len += part.len() as i64 + 1;
    }
    if !line.is_empty() {
        lines.push(format!("{pad}{}", line.join(" ")));
    }
    if prefix {
        lines[0] = lines[0][indent..].to_string();
    }
    lines
}

fn usage(text_width: i64) -> String {
    let mut usage = format!("{PROG} {} {}", OPT_PARTS.join(" "), POS_PARTS.join(" "));
    if (PREFIX.len() + usage.len()) as i64 > text_width {
        let lines = if (PREFIX.len() + PROG.len()) as f64 <= 0.75 * text_width as f64 {
            let indent = PREFIX.len() + PROG.len() + 1;
            let mut first = vec![PROG];
            first.extend(OPT_PARTS);
            let mut lines = get_lines(&first, indent, true, text_width);
            lines.extend(get_lines(&POS_PARTS, indent, false, text_width));
            lines
        } else {
            let indent = PREFIX.len();
            let all: Vec<&str> = OPT_PARTS.iter().chain(POS_PARTS.iter()).copied().collect();
            let mut lines = get_lines(&all, indent, false, text_width);
            if lines.len() > 1 {
                lines = get_lines(&OPT_PARTS, indent, false, text_width);
                lines.extend(get_lines(&POS_PARTS, indent, false, text_width));
            }
            lines.insert(0, PROG.to_string());
            lines
        };
        usage = lines.join("\n");
    }
    format!("{PREFIX}{usage}\n\n")
}

/// `parser.format_help()` (columns 는 터미널 폭)
pub fn help_text(columns: i64) -> String {
    let width = columns.clamp(-MAX_COLUMNS, MAX_COLUMNS) - 2;
    let max_help_position = 24.min((width - 20).max(4));
    let help_position = (ACTION_MAX_LENGTH + 2).min(max_help_position);
    let help_width = (width - help_position).max(11);
    let action_width = help_position - 2 - 2;
    let pad = |n: i64| " ".repeat(n.max(0) as usize);

    let mut text = String::from("\n");
    text += &usage(width);
    text += &wrap(DESCRIPTION, width.max(11)).join("\n");
    text += "\n\n";
    for (heading, actions) in SECTIONS {
        text += &format!("\n{heading}:\n");
        for &(header, help) in actions {
            let Some(help) = help else {
                text += &format!("  {header}\n");
                continue;
            };
            let lines = wrap(help, help_width);
            if header.len() as i64 <= action_width {
                text += &format!(
                    "  {header}{}  {}\n",
                    pad(action_width - header.len() as i64),
                    lines[0]
                );
            } else {
                text += &format!("  {header}\n{}{}\n", pad(help_position), lines[0]);
            }
            for line in &lines[1..] {
                text += &format!("{}{line}\n", pad(help_position));
            }
        }
        text += "\n";
    }
    text += "\n";
    // re.sub('\n\n\n+', '\n\n') 후 strip('\n') + '\n'
    while text.contains("\n\n\n") {
        text = text.replace("\n\n\n", "\n\n");
    }
    format!("{}\n", text.trim_matches('\n'))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_width_matches_python() {
        // verify/help_text.py 로 얻은 80열 출력
        assert_eq!(
            help_text(80),
            "usage: logstat [-h] [--format {csv,jsonl}] [--top TOP] [--json] [--strict]\n               file\n\n\
             Summarize CSV or JSON Lines access logs.\n\npositional arguments:\n  file\n\noptions:\n  \
             -h, --help            show this help message and exit\n  --format {csv,jsonl}  default: from the file \
             extension\n  --top TOP\n  --json\n  --strict              stop at the first bad record\n"
        );
    }

    #[test]
    fn python_int_rules() {
        assert_eq!(python_int(" 1_000 "), Some(1000));
        assert_eq!(python_int("+7"), Some(7));
        assert_eq!(python_int("-5"), Some(-5));
        assert_eq!(python_int("١٢"), Some(12));
        assert_eq!(python_int("\u{3000}40\u{a0}"), Some(40));
        assert_eq!(python_int("1__0"), None);
        assert_eq!(python_int("_1"), None);
        assert_eq!(python_int("\u{1c}1"), None);
        assert_eq!(python_int(""), None);
        assert_eq!(python_int("abc"), None);
    }
}
