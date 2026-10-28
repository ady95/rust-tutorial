//! 명령행 해석 (계약 1절). Python 기준 구현의 argparse(CPython 3.12) 동작을 옮겼다.
//!
//! 계약은 인자 오류의 stderr 내용을 비교하지 않지만, 어떤 입력이 정상 실행(0)·도움말(0)·
//! 인자 오류(2) 중 어디로 가는지는 종료 코드로 드러나므로 argparse 와 같게 맞춘다.
//! 긴 옵션의 접두어 축약(--to 5), `--top=5`, `-hh`, `--` 구분자, 음수처럼 보이는 인자 등이 그 예이다.

use std::ffi::OsString;

use crate::pystr;

pub const USAGE: &str = "usage: wordfreq [-h] [--top TOP] [--json] file\n";

pub const HELP: &str = "\
usage: wordfreq [-h] [--top TOP] [--json] file

Count word frequencies.

positional arguments:
  file        UTF-8 text file

options:
  -h, --help  show this help message and exit
  --top TOP   number of words (default 10)
  --json      print JSON instead of text
";

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
    /// argparse 가 `wordfreq: error: ` 뒤에 붙이는 메시지.
    Error(String),
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum Opt {
    Help,
    Top,
    Json,
}

/// argparse 에 등록된 순서 그대로의 옵션 문자열.
const OPTIONS: [(&str, Opt); 4] = [("-h", Opt::Help), ("--help", Opt::Help), ("--top", Opt::Top), ("--json", Opt::Json)];

/// argparse 가 각 인자에 붙이는 분류 ('O', 'A', '-').
#[derive(Debug)]
enum Kind {
    /// 옵션. 모르는 옵션이면 opt 가 None.
    Optional { opt: Option<(Opt, &'static str)>, explicit: Option<String> },
    Positional,
    /// 처음 나온 `--`.
    Separator,
}

/// 해석이 일찍 끝나는 경우 (도움말 출력 또는 인자 오류).
enum Stop {
    Help,
    Error(String),
}

pub fn parse(argv: &[OsString]) -> Parsed {
    match parse_args(argv) {
        Ok(args) => Parsed::Run(args),
        Err(Stop::Help) => Parsed::Help,
        Err(Stop::Error(message)) => Parsed::Error(message),
    }
}

fn parse_args(argv: &[OsString]) -> Result<Args, Stop> {
    let strings: Vec<String> = argv.iter().map(|arg| arg.to_string_lossy().into_owned()).collect();

    // argparse 는 먼저 모든 인자를 분류한다. 모호한 옵션 오류는 이 단계에서 난다.
    let mut kinds = Vec::with_capacity(strings.len());
    let mut separated = false;
    for s in &strings {
        let kind = if separated {
            Kind::Positional
        } else if s == "--" {
            separated = true;
            Kind::Separator
        } else {
            classify(s).map_err(Stop::Error)?
        };
        kinds.push(kind);
    }

    let mut file = None;
    let mut top = 10;
    let mut json = false;
    let mut extras: Vec<&str> = Vec::new();
    let mut i = 0;
    while i < kinds.len() {
        match &kinds[i] {
            Kind::Optional { opt: None, .. } => {
                extras.push(&strings[i]);
                i += 1;
            }
            Kind::Optional { opt: Some((opt, option_string)), explicit } => {
                i = match (opt, explicit) {
                    (Opt::Top, Some(value)) => {
                        top = positive_int(value)?;
                        i + 1
                    }
                    (Opt::Top, None) => match (kinds.get(i + 1), strings.get(i + 1)) {
                        (Some(Kind::Positional), Some(value)) => {
                            top = positive_int(value)?;
                            i + 2
                        }
                        _ => return Err(error("argument --top: expected one argument")),
                    },
                    (Opt::Json, None) => {
                        json = true;
                        i + 1
                    }
                    (Opt::Help, None) => return Err(Stop::Help),
                    // 값을 받지 않는 옵션에 값이 붙은 경우. `-hh` 처럼 짧은 옵션을 이어 쓴 것만 허용된다.
                    (Opt::Help, Some(rest)) if *option_string == "-h" && !rest.is_empty() && rest.chars().all(|c| c == 'h') => {
                        return Err(Stop::Help);
                    }
                    (opt, Some(rest)) => {
                        let name = if *opt == Opt::Help { "-h/--help" } else { "--json" };
                        return Err(error(&format!("argument {name}: ignored explicit argument '{rest}'")));
                    }
                };
            }
            // 위치 인자 패턴은 `-*A-*` 이다. 처음 나온 `--` 는 FILE 바로 앞이나 뒤에 붙어 있을 때만 흡수된다.
            Kind::Separator if file.is_none() && matches!(kinds.get(i + 1), Some(Kind::Positional)) => {
                file = Some(argv[i + 1].clone());
                i += 2;
            }
            Kind::Positional if file.is_none() => {
                file = Some(argv[i].clone());
                i += if matches!(kinds.get(i + 1), Some(Kind::Separator)) { 2 } else { 1 };
            }
            Kind::Separator | Kind::Positional => {
                extras.push(&strings[i]);
                i += 1;
            }
        }
    }

    let Some(file) = file else {
        return Err(error("the following arguments are required: file"));
    };
    if !extras.is_empty() {
        return Err(error(&format!("unrecognized arguments: {}", extras.join(" "))));
    }
    Ok(Args { file, top, json })
}

fn error(message: &str) -> Stop {
    Stop::Error(message.to_string())
}

fn lookup(option_string: &str) -> Option<(Opt, &'static str)> {
    OPTIONS.iter().find(|(name, _)| *name == option_string).map(|&(name, opt)| (opt, name))
}

/// argparse `_parse_optional`: 인자가 옵션인지 위치 인자인지 가른다.
fn classify(s: &str) -> Result<Kind, String> {
    let optional = |opt, explicit: Option<&str>| Kind::Optional { opt, explicit: explicit.map(str::to_string) };

    if !s.starts_with('-') {
        return Ok(Kind::Positional);
    }
    if let Some(found) = lookup(s) {
        return Ok(optional(Some(found), None));
    }
    if s.chars().count() == 1 {
        return Ok(Kind::Positional);
    }
    if let Some((name, value)) = s.split_once('=')
        && let Some(found) = lookup(name)
    {
        return Ok(optional(Some(found), Some(value)));
    }

    let mut matches = option_tuples(s);
    if matches.len() > 1 {
        let names: Vec<&str> = matches.iter().map(|((_, name), _)| *name).collect();
        return Err(format!("ambiguous option: {s} could match {}", names.join(", ")));
    }
    if let Some((found, explicit)) = matches.pop() {
        return Ok(optional(Some(found), explicit));
    }

    // 음수처럼 보이는 인자는, 음수 모양 옵션이 없는 파서에서는 위치 인자다.
    if looks_like_negative_number(s) || s.contains(' ') {
        return Ok(Kind::Positional);
    }
    Ok(optional(None, None))
}

/// argparse `_get_option_tuples`: 긴 옵션은 접두어로, 짧은 옵션은 뒤에 값이 붙은 형태로 찾는다.
fn option_tuples(s: &str) -> Vec<((Opt, &'static str), Option<&str>)> {
    let mut result = Vec::new();
    if s[1..].starts_with('-') {
        let (prefix, explicit) = match s.split_once('=') {
            Some((prefix, value)) => (prefix, Some(value)),
            None => (s, None),
        };
        for &(name, opt) in &OPTIONS {
            if name.starts_with(prefix) {
                result.push(((opt, name), explicit));
            }
        }
    } else {
        let split = s.char_indices().nth(2).map_or(s.len(), |(index, _)| index);
        let (short_prefix, short_explicit) = s.split_at(split);
        for &(name, opt) in &OPTIONS {
            if name == short_prefix {
                result.push(((opt, name), Some(short_explicit)));
            } else if name.starts_with(s) {
                result.push(((opt, name), None));
            }
        }
    }
    result
}

/// argparse 의 `^-\d+$|^-\d*\.\d+$`. `\d` 는 Unicode 십진 숫자, `$` 는 끝 줄바꿈 하나 앞에서도 맞는다.
fn looks_like_negative_number(s: &str) -> bool {
    let s = s.strip_suffix('\n').unwrap_or(s);
    let Some(body) = s.strip_prefix('-') else {
        return false;
    };
    let all_digits = |part: &str| part.chars().all(|c| pystr::decimal_value(c).is_some());
    match body.split_once('.') {
        None => !body.is_empty() && all_digits(body),
        Some((whole, fraction)) => all_digits(whole) && !fraction.is_empty() && all_digits(fraction),
    }
}

/// 기준 구현의 `positive_int`.
fn positive_int(value: &str) -> Result<usize, Stop> {
    match pystr::int(value) {
        None => Err(error(&format!("argument --top: not an integer: {value}"))),
        Some(number) if number < 1 => Err(error(&format!("argument --top: must be at least 1: {value}"))),
        Some(number) => Ok(usize::try_from(number).unwrap_or(usize::MAX)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(args: &[&str]) -> Parsed {
        parse(&args.iter().map(OsString::from).collect::<Vec<_>>())
    }

    fn ok(file: &str, top: usize, json: bool) -> Parsed {
        Parsed::Run(Args { file: file.into(), top, json })
    }

    fn is_error(parsed: Parsed) -> bool {
        matches!(parsed, Parsed::Error(_))
    }

    #[test]
    fn defaults_and_options() {
        assert_eq!(run(&["a.txt"]), ok("a.txt", 10, false));
        assert_eq!(run(&["--top", "2", "a.txt", "--json"]), ok("a.txt", 2, true));
        assert_eq!(run(&["a.txt", "--top=3"]), ok("a.txt", 3, false));
        assert_eq!(run(&["a.txt", "--top", "2", "--top", "5"]), ok("a.txt", 5, false));
    }

    #[test]
    fn long_options_can_be_abbreviated() {
        assert_eq!(run(&["a.txt", "--t", "4", "--j"]), ok("a.txt", 4, true));
        assert_eq!(run(&["a.txt", "--to=4"]), ok("a.txt", 4, false));
        assert_eq!(run(&["a.txt", "--he"]), Parsed::Help);
    }

    #[test]
    fn top_accepts_what_python_int_accepts() {
        assert_eq!(run(&["a.txt", "--top", " 7 "]), ok("a.txt", 7, false));
        assert_eq!(run(&["a.txt", "--top", "1_0"]), ok("a.txt", 10, false));
        assert_eq!(run(&["a.txt", "--top", "３"]), ok("a.txt", 3, false));
        assert_eq!(run(&["a.txt", "--top", "99999999999999999999999"]), ok("a.txt", usize::MAX, false));
    }

    #[test]
    fn help_wins_only_if_reached_before_an_error() {
        assert_eq!(run(&["-h"]), Parsed::Help);
        assert_eq!(run(&["--bogus", "-h"]), Parsed::Help);
        assert_eq!(run(&["-hh"]), Parsed::Help);
        assert!(is_error(run(&["--top", "0", "-h"])));
        assert!(is_error(run(&["-hx"])));
        assert!(is_error(run(&["--help=x"])));
        assert!(is_error(run(&["-h", "--=x"])), "ambiguous options fail before anything runs");
    }

    #[test]
    fn usage_errors() {
        for args in [
            &[][..],
            &["a.txt", "--top", "0"],
            &["a.txt", "--top", "abc"],
            &["a.txt", "--top", "-5"],
            &["a.txt", "--top"],
            &["a.txt", "--top", "--json"],
            &["a.txt", "--bogus"],
            &["a.txt", "b.txt"],
            &["a.txt", "--json=1"],
            &["a.txt", "--json", "--"],
        ] {
            assert!(is_error(run(args)), "{args:?}");
        }
    }

    #[test]
    fn positional_edge_cases() {
        assert_eq!(run(&["-"]), ok("-", 10, false));
        assert_eq!(run(&["-5"]), ok("-5", 10, false));
        assert_eq!(run(&["-x y"]), ok("-x y", 10, false));
        assert_eq!(run(&[""]), ok("", 10, false));
        assert_eq!(run(&["--", "--json"]), ok("--json", 10, false));
        assert_eq!(run(&["a.txt", "--"]), ok("a.txt", 10, false));
        assert_eq!(run(&["--json", "--", "-a"]), ok("-a", 10, true));
    }
}
