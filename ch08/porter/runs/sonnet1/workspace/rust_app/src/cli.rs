//! Python argparse(3.12) 와 같은 규칙으로 명령행을 해석하는 작은 파서.

use crate::py_tables::{in_table, DIGITS};
use std::ffi::OsString;

const DEFAULT_TOP: usize = 10;
/// 이보다 자릿수가 많으면 "아주 큰 수"로 본다 (기준 구현의 MAX_TOP_DIGITS)
const MAX_TOP_DIGITS: usize = 18;

pub const USAGE: &str = "usage: wordfreq [-h] [--top TOP] [--json] file\n";
pub const HELP: &str = "usage: wordfreq [-h] [--top TOP] [--json] file\n\n\
Count word frequencies.\n\n\
positional arguments:\n  file         UTF-8 text file\n\n\
options:\n  -h, --help   show this help message and exit\n  \
--top TOP    number of words (default 10)\n  \
--json       print JSON instead of text\n";

#[derive(Debug, PartialEq)]
pub struct Args {
    pub file: OsString,
    pub top: usize,
    pub json: bool,
}

#[derive(Debug, PartialEq)]
pub enum Parsed {
    Run(Args),
    Help,
    /// 인자 오류. 값은 stderr 에 쓸 메시지
    Usage(String),
}

#[derive(Clone, Copy, PartialEq)]
enum Opt {
    Top,
    Json,
    Help,
}

enum Kind {
    Positional,
    Unknown,
    Ambiguous,
    /// 옵션과 `=` 뒤(또는 짧은 옵션 뒤에 붙은) 값
    Option(Opt, Option<Vec<u8>>),
}

const LONG_OPTIONS: [(&[u8], Opt); 3] = [
    (b"--top", Opt::Top),
    (b"--json", Opt::Json),
    (b"--help", Opt::Help),
];

/// 계약 1절: ASCII 숫자만, 앞의 0은 무시, 0은 오류, 아주 큰 값은 usize::MAX
pub fn positive_int(value: &[u8]) -> Result<usize, String> {
    let shown = String::from_utf8_lossy(value);
    if value.is_empty() || !value.iter().all(u8::is_ascii_digit) {
        return Err(format!("argument --top: not an integer: {shown}"));
    }
    let start = value.iter().take_while(|&&b| b == b'0').count();
    let digits = &value[start..];
    if digits.is_empty() {
        return Err(format!("argument --top: must be at least 1: {shown}"));
    }
    if digits.len() > MAX_TOP_DIGITS {
        return Ok(usize::MAX);
    }
    let n = digits
        .iter()
        .fold(0u64, |acc, &b| acc * 10 + u64::from(b - b'0'));
    Ok(usize::try_from(n).unwrap_or(usize::MAX))
}

/// argparse 의 `^-\d+$|^-\d*\.\d+$` (`$` 는 끝의 개행 하나도 허용)
fn looks_like_negative_number(arg: &[u8]) -> bool {
    // \d 는 Unicode 숫자(Nd)를 모두 받는다. UTF-8 이 아닌 바이트(서로게이트)는 숫자가 아니다
    let Ok(arg) = std::str::from_utf8(arg) else {
        return false;
    };
    let arg = arg.strip_suffix('\n').unwrap_or(arg);
    let Some(rest) = arg.strip_prefix('-') else {
        return false;
    };
    let all_digits = |s: &str| s.chars().all(|c| in_table(DIGITS, c));
    if !rest.is_empty() && all_digits(rest) {
        return true;
    }
    match rest.split_once('.') {
        Some((int, frac)) => all_digits(int) && !frac.is_empty() && all_digits(frac),
        None => false,
    }
}

/// argparse 의 _parse_optional
fn classify(arg: &[u8]) -> Kind {
    if arg.len() < 2 || arg[0] != b'-' {
        return Kind::Positional;
    }
    if arg == b"-h" {
        return Kind::Option(Opt::Help, None);
    }
    if let Some((_, opt)) = LONG_OPTIONS.iter().find(|(name, _)| *name == arg) {
        return Kind::Option(*opt, None);
    }
    if let Some(eq) = arg.iter().position(|&b| b == b'=') {
        let (name, value) = (&arg[..eq], &arg[eq + 1..]);
        if name == b"-h" {
            return Kind::Option(Opt::Help, Some(value.to_vec()));
        }
        if let Some((_, opt)) = LONG_OPTIONS.iter().find(|(n, _)| *n == name) {
            return Kind::Option(*opt, Some(value.to_vec()));
        }
    }
    if arg[1] == b'-' {
        let (prefix, explicit) = match arg.iter().position(|&b| b == b'=') {
            Some(eq) => (&arg[..eq], Some(arg[eq + 1..].to_vec())),
            None => (arg, None),
        };
        let matches: Vec<Opt> = LONG_OPTIONS
            .iter()
            .filter(|(name, _)| name.starts_with(prefix))
            .map(|(_, opt)| *opt)
            .collect();
        match matches.as_slice() {
            [] => {}
            [opt] => return Kind::Option(*opt, explicit),
            _ => return Kind::Ambiguous,
        }
    } else if arg.starts_with(b"-h") {
        // `-hx`, `-hh` 는 도움말로 끝난다 (3.12.3 에서 확인). `-h=x` 만 오류다
        return Kind::Option(Opt::Help, None);
    }
    if looks_like_negative_number(arg) || arg.contains(&b' ') {
        return Kind::Positional;
    }
    Kind::Unknown
}

fn os_from_bytes(bytes: &[u8]) -> OsString {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStringExt;
        OsString::from_vec(bytes.to_vec())
    }
    #[cfg(not(unix))]
    {
        OsString::from(String::from_utf8_lossy(bytes).into_owned())
    }
}

pub fn os_to_bytes(arg: &std::ffi::OsStr) -> Vec<u8> {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        arg.as_bytes().to_vec()
    }
    #[cfg(not(unix))]
    {
        arg.to_string_lossy().into_owned().into_bytes()
    }
}

/// 오류 메시지에 넣을 이름. UTF-8 이 아닌 바이트는 U+FFFD 로 바꾼다 (계약 4절)
pub fn display_name(arg: &std::ffi::OsStr) -> String {
    String::from_utf8_lossy(&os_to_bytes(arg)).into_owned()
}

pub fn parse<I: IntoIterator<Item = OsString>>(args: I) -> Parsed {
    let args: Vec<Vec<u8>> = args.into_iter().map(|a| os_to_bytes(&a)).collect();
    let mut files: Vec<&[u8]> = Vec::new();
    let mut unrecognized = false;
    let mut top = DEFAULT_TOP;
    let mut json = false;
    let mut i = 0;
    while i < args.len() {
        let arg = args[i].as_slice();
        i += 1;
        if arg == b"--" {
            files.extend(args[i..].iter().map(Vec::as_slice));
            break;
        }
        let (opt, explicit) = match classify(arg) {
            Kind::Positional => {
                files.push(arg);
                continue;
            }
            Kind::Unknown => {
                unrecognized = true;
                continue;
            }
            Kind::Ambiguous => {
                let shown = String::from_utf8_lossy(arg);
                return Parsed::Usage(format!("ambiguous option: {shown}"));
            }
            Kind::Option(opt, explicit) => (opt, explicit),
        };
        match opt {
            Opt::Help => {
                if explicit.is_some() {
                    return Parsed::Usage("ignored explicit argument".to_string());
                }
                return Parsed::Help;
            }
            Opt::Json => {
                if explicit.is_some() {
                    return Parsed::Usage("argument --json: ignored explicit argument".to_string());
                }
                json = true;
            }
            Opt::Top => {
                let value: &[u8] = match explicit.as_deref() {
                    Some(v) => v,
                    None => {
                        // 다음 인자가 옵션 모양이면(`--` 포함) 값이 없는 것이다
                        match args.get(i) {
                            Some(v) if matches!(classify(v), Kind::Positional) => {
                                i += 1;
                                v.as_slice()
                            }
                            _ => {
                                return Parsed::Usage(
                                    "argument --top: expected one argument".to_string(),
                                )
                            }
                        }
                    }
                };
                match positive_int(value) {
                    Ok(n) => top = n,
                    Err(message) => return Parsed::Usage(message),
                }
            }
        }
    }
    match files.as_slice() {
        [] => Parsed::Usage("the following arguments are required: file".to_string()),
        [file] if !unrecognized => Parsed::Run(Args {
            file: os_from_bytes(file),
            top,
            json,
        }),
        _ => Parsed::Usage("unrecognized arguments".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(args: &[&str]) -> Parsed {
        parse(args.iter().map(OsString::from))
    }

    fn ok(file: &str, top: usize, json: bool) -> Parsed {
        Parsed::Run(Args {
            file: OsString::from(file),
            top,
            json,
        })
    }

    fn is_usage(p: Parsed) -> bool {
        matches!(p, Parsed::Usage(_))
    }

    #[test]
    fn basic_forms() {
        assert_eq!(run(&["a.txt"]), ok("a.txt", 10, false));
        assert_eq!(
            run(&["a.txt", "--top", "3", "--json"]),
            ok("a.txt", 3, true)
        );
        assert_eq!(run(&["--top=1", "a.txt"]), ok("a.txt", 1, false));
        assert_eq!(run(&["--to", "2", "a.txt"]), ok("a.txt", 2, false));
        assert_eq!(run(&["--js", "a.txt"]), ok("a.txt", 10, true));
        assert_eq!(run(&["--t=2", "a.txt"]), ok("a.txt", 2, false));
        assert_eq!(
            run(&["a.txt", "--top", "1", "--top", "2"]),
            ok("a.txt", 2, false)
        );
    }

    #[test]
    fn dash_and_double_dash() {
        assert_eq!(run(&["-"]), ok("-", 10, false));
        assert_eq!(run(&["--", "-x"]), ok("-x", 10, false));
        assert_eq!(run(&["-5"]), ok("-5", 10, false));
        assert_eq!(run(&["-1.5"]), ok("-1.5", 10, false));
        assert_eq!(run(&["-٣"]), ok("-٣", 10, false));
        assert!(is_usage(run(&["-٣x"])));
        assert_eq!(run(&["-x y"]), ok("-x y", 10, false));
        assert!(is_usage(run(&["a.txt", "--top", "--", "5"])));
    }

    #[test]
    fn usage_errors() {
        assert!(is_usage(run(&[])));
        assert!(is_usage(run(&["-x.txt"])));
        assert!(is_usage(run(&["a", "b"])));
        assert!(is_usage(run(&["a", "--json=1"])));
        assert!(is_usage(run(&["a", "--top"])));
        assert!(is_usage(run(&["a", "--top", "0", "--top", "2"])));
        assert!(is_usage(run(&["a", "--top", "--json"])));
        assert!(is_usage(run(&["a", "--=x"])));
    }

    #[test]
    fn help_wins_over_deferred_errors() {
        assert_eq!(run(&["-h"]), Parsed::Help);
        assert_eq!(run(&["-x", "--help"]), Parsed::Help);
        assert_eq!(run(&["--he"]), Parsed::Help);
        assert!(is_usage(run(&["--top", "abc", "--help"])));
        assert!(is_usage(run(&["--help=1"])));
    }

    #[test]
    fn positive_int_rules() {
        assert_eq!(positive_int(b"007"), Ok(7));
        assert_eq!(
            positive_int(b"999999999999999999"),
            Ok(999_999_999_999_999_999)
        );
        assert_eq!(positive_int(b"1000000000000000000"), Ok(usize::MAX));
        assert_eq!(positive_int(&[b'9'; 5000]), Ok(usize::MAX));
        for bad in [
            "", "0", "000", "+3", " 3", "3 ", "-1", "1_0", "٣", "２", "abc",
        ] {
            assert!(positive_int(bad.as_bytes()).is_err(), "{bad:?}");
        }
    }
}
