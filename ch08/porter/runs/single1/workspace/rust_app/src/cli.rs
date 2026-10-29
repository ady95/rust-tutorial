//! 명령행 처리(계약 1절). 기준 구현이 쓰는 argparse(Python 3.12.3)의 parse_args 순서를 그대로 따른다.
//!
//! 흉내 내는 argparse 동작: '--' 뒤는 모두 위치 인자, '-' 하나는 위치 인자, '--top=1',
//! --top 반복 시 마지막 값(값마다 검사), 긴 옵션 접두어 약어(--to, --js), 음수 모양이거나 공백이 든
//! '-' 시작 문자열은 위치 인자, -h/--help 는 stdout 에 도움말을 쓰고 0.

use std::borrow::Cow;
use std::ffi::{OsStr, OsString};

pub const USAGE: &str = "usage: wordfreq [-h] [--top TOP] [--json] file\n";

pub const HELP: &str = "usage: wordfreq [-h] [--top TOP] [--json] file

Count word frequencies.

positional arguments:
  file        UTF-8 text file

options:
  -h, --help  show this help message and exit
  --top TOP   number of words (default 10)
  --json      print JSON instead of text
";

/// --top 이 이보다 큰 자릿수면 그냥 "아주 큰 수"로 본다 (기준 구현의 MAX_TOP_DIGITS)
const MAX_TOP_DIGITS: usize = 18;

#[derive(Debug, PartialEq, Eq)]
pub struct Args {
    pub file: OsString,
    pub top: usize,
    pub json: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Outcome {
    Run(Args),
    /// -h/--help: 도움말을 stdout 에 쓰고 0
    Help,
    /// 인자 오류: 메시지를 stderr 에 쓰고 2
    Usage(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Action {
    Help,
    Top,
    Json,
}

/// argparse 의 _option_string_actions (등록 순서)
const OPTIONS: [(&[u8], Action); 4] = [
    (b"-h", Action::Help),
    (b"--help", Action::Help),
    (b"--top", Action::Top),
    (b"--json", Action::Json),
];

fn lookup(name: &[u8]) -> Option<Action> {
    OPTIONS.iter().find(|(n, _)| *n == name).map(|&(_, a)| a)
}

/// argparse 의 option_tuple: (action, option_string, sep, explicit_arg)
#[derive(Debug, Clone)]
struct OptTuple {
    action: Option<Action>,
    option: Vec<u8>,
    /// sep 가 '=' 이면 true (None 과 '' 는 false)
    sep_eq: bool,
    explicit: Option<Vec<u8>>,
}

/// arg_strings_pattern 의 한 글자: 'A', '-'('--' 구분자), 'O'
#[derive(Debug, Clone)]
enum Slot {
    Arg,
    Sep,
    Opt(OptTuple),
}

enum Stop {
    Help,
    Usage(String),
}

/// 인자의 원래 바이트. Python 은 surrogateescape 로 바이트를 보존하므로 UTF-8 이 아니어도 그대로 비교한다
pub fn arg_bytes(arg: &OsStr) -> Cow<'_, [u8]> {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        Cow::Borrowed(arg.as_bytes())
    }
    #[cfg(not(unix))]
    {
        match arg.to_string_lossy() {
            Cow::Borrowed(s) => Cow::Borrowed(s.as_bytes()),
            Cow::Owned(s) => Cow::Owned(s.into_bytes()),
        }
    }
}

/// 오류 메시지에 넣을 파일 이름. UTF-8 이 아닌 바이트는 최대 부분마다 U+FFFD 로 바꾼다 (계약 4절)
pub fn display_name(arg: &OsStr) -> String {
    String::from_utf8_lossy(&arg_bytes(arg)).into_owned()
}

/// 기준 구현의 positive_int: ASCII 숫자만, 앞의 0 무시, 0 은 오류, 18자리 넘으면 아주 큰 수
pub fn positive_int(value: &[u8]) -> Result<usize, String> {
    let shown = String::from_utf8_lossy(value);
    if value.is_empty() || !value.iter().all(u8::is_ascii_digit) {
        return Err(format!("not an integer: {shown}"));
    }
    let start = value.iter().position(|&b| b != b'0').unwrap_or(value.len());
    let digits = &value[start..];
    if digits.is_empty() {
        return Err(format!("must be at least 1: {shown}"));
    }
    if digits.len() > MAX_TOP_DIGITS {
        return Ok(usize::MAX);
    }
    let n = digits
        .iter()
        .fold(0u64, |acc, &d| acc * 10 + u64::from(d - b'0'));
    Ok(usize::try_from(n).unwrap_or(usize::MAX))
}

/// Unicode 15.0 의 일반 범주 Nd 각 묶음(10자)의 첫 글자. Python re 의 \d 와 같다
const ND_ZEROS: &[u32] = &[
    0x30, 0x660, 0x6F0, 0x7C0, 0x966, 0x9E6, 0xA66, 0xAE6, 0xB66, 0xBE6, 0xC66, 0xCE6, 0xD66,
    0xDE6, 0xE50, 0xED0, 0xF20, 0x1040, 0x1090, 0x17E0, 0x1810, 0x1946, 0x19D0, 0x1A80, 0x1A90,
    0x1B50, 0x1BB0, 0x1C40, 0x1C50, 0xA620, 0xA8D0, 0xA900, 0xA9D0, 0xA9F0, 0xAA50, 0xABF0, 0xFF10,
    0x104A0, 0x10D30, 0x11066, 0x110F0, 0x11136, 0x111D0, 0x112F0, 0x11450, 0x114D0, 0x11650,
    0x116C0, 0x11730, 0x118E0, 0x11950, 0x11C50, 0x11D50, 0x11DA0, 0x11F50, 0x16A60, 0x16AC0,
    0x16B50, 0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6, 0x1E140, 0x1E2F0, 0x1E4F0, 0x1E950,
    0x1FBF0,
];

fn is_re_digit(c: char) -> bool {
    let n = c as u32;
    ND_ZEROS.iter().any(|&z| z <= n && n < z + 10)
}

/// argparse 의 _negative_number_matcher: r'^-\d+$|^-\d*\.\d+$' (re 의 $ 는 끝의 '\n' 하나 앞에서도 맞는다)
fn looks_negative(arg: &[u8]) -> bool {
    let text = String::from_utf8_lossy(arg);
    let text = text.strip_suffix('\n').unwrap_or(&text);
    let Some(body) = text.strip_prefix('-') else {
        return false;
    };
    let all_digits = |s: &str| s.chars().all(is_re_digit);
    if !body.is_empty() && all_digits(body) {
        return true;
    }
    match body.split_once('.') {
        Some((int, frac)) => all_digits(int) && !frac.is_empty() && all_digits(frac),
        None => false,
    }
}

fn split_eq(arg: &[u8]) -> Option<(&[u8], &[u8])> {
    let eq = arg.iter().position(|&b| b == b'=')?;
    Some((&arg[..eq], &arg[eq + 1..]))
}

/// argparse 의 _get_option_tuples (allow_abbrev=True)
fn option_tuples(arg: &[u8]) -> Vec<OptTuple> {
    let mut result = Vec::new();
    if arg[1] == b'-' {
        let (prefix, explicit) = match split_eq(arg) {
            Some((p, e)) => (p, Some(e.to_vec())),
            None => (arg, None),
        };
        for &(name, action) in &OPTIONS {
            if name.starts_with(prefix) {
                result.push(OptTuple {
                    action: Some(action),
                    option: name.to_vec(),
                    sep_eq: explicit.is_some(),
                    explicit: explicit.clone(),
                });
            }
        }
    } else {
        // 짧은 옵션은 뒤에 값을 붙여 쓸 수 있다(-hx). 글자 단위로 자르지만 '-h' 와 같은지만 보므로 바이트로 충분하다
        for &(name, action) in &OPTIONS {
            if name == &arg[..2] {
                result.push(OptTuple {
                    action: Some(action),
                    option: name.to_vec(),
                    sep_eq: false,
                    explicit: Some(arg[2..].to_vec()),
                });
            } else if name.starts_with(arg) {
                result.push(OptTuple {
                    action: Some(action),
                    option: name.to_vec(),
                    sep_eq: false,
                    explicit: None,
                });
            }
        }
    }
    result
}

/// argparse 의 _parse_optional. None 이면 위치 인자
fn parse_optional(arg: &[u8]) -> Result<Option<OptTuple>, Stop> {
    if arg.first() != Some(&b'-') {
        return Ok(None);
    }
    if let Some(action) = lookup(arg) {
        return Ok(Some(OptTuple {
            action: Some(action),
            option: arg.to_vec(),
            sep_eq: false,
            explicit: None,
        }));
    }
    if arg.len() == 1 {
        return Ok(None);
    }
    if let Some((name, value)) = split_eq(arg) {
        if let Some(action) = lookup(name) {
            return Ok(Some(OptTuple {
                action: Some(action),
                option: name.to_vec(),
                sep_eq: true,
                explicit: Some(value.to_vec()),
            }));
        }
    }
    let mut tuples = option_tuples(arg);
    if tuples.len() > 1 {
        return Err(Stop::Usage(format!(
            "ambiguous option: {}",
            String::from_utf8_lossy(arg)
        )));
    }
    if let Some(tuple) = tuples.pop() {
        return Ok(Some(tuple));
    }
    if looks_negative(arg) || arg.contains(&b' ') {
        return Ok(None);
    }
    Ok(Some(OptTuple {
        action: None,
        option: arg.to_vec(),
        sep_eq: false,
        explicit: None,
    }))
}

/// nargs=None 의 패턴 '(-*A-*)' 가 맞는 길이
fn match_one(slots: &[Slot]) -> Option<usize> {
    let lead = slots.iter().take_while(|s| matches!(s, Slot::Sep)).count();
    if !matches!(slots.get(lead), Some(Slot::Arg)) {
        return None;
    }
    let trail = slots[lead + 1..]
        .iter()
        .take_while(|s| matches!(s, Slot::Sep))
        .count();
    Some(lead + 1 + trail)
}

/// nargs=0 의 패턴 '(-*-*)' 가 맞는 길이
fn match_zero(slots: &[Slot]) -> usize {
    slots.iter().take_while(|s| matches!(s, Slot::Sep)).count()
}

struct Parser<'a> {
    argv: Vec<Cow<'a, [u8]>>,
    raw: &'a [OsString],
    slots: Vec<Slot>,
    file: Option<OsString>,
    top: usize,
    json: bool,
    extras: usize,
}

impl Parser<'_> {
    fn take_action(&mut self, action: Action, values: &[Vec<u8>]) -> Result<(), Stop> {
        match action {
            Action::Help => return Err(Stop::Help),
            Action::Json => self.json = true,
            Action::Top => {
                // 값이 둘이면('--' 포함) argparse 는 각각을 positive_int 로 바꾸다 '--' 에서 실패한다
                for value in values {
                    match positive_int(value) {
                        Ok(n) => self.top = n,
                        Err(msg) => return Err(Stop::Usage(format!("argument --top: {msg}"))),
                    }
                }
            }
        }
        Ok(())
    }

    /// argparse 의 consume_optional. 모은 동작은 끝에서 차례로 실행한다(도중의 오류가 먼저다)
    fn consume_optional(&mut self, start: usize) -> Result<usize, Stop> {
        let Slot::Opt(tuple) = self.slots[start].clone() else {
            return Ok(start + 1);
        };
        let Some(mut action) = tuple.action else {
            self.extras += 1;
            return Ok(start + 1);
        };
        let mut option = tuple.option;
        let mut sep_eq = tuple.sep_eq;
        let mut explicit = tuple.explicit;
        let mut pending: Vec<(Action, Vec<Vec<u8>>)> = Vec::new();
        let stop = loop {
            let Some(value) = explicit.take() else {
                let rest = &self.slots[start + 1..];
                let count = match action {
                    Action::Top => match_one(rest).ok_or_else(|| {
                        Stop::Usage("argument --top: expected one argument".into())
                    })?,
                    Action::Help | Action::Json => match_zero(rest),
                };
                let values = (start + 1..start + 1 + count)
                    .map(|i| self.argv[i].to_vec())
                    .collect();
                pending.push((action, values));
                break start + 1 + count;
            };
            let arg_count = usize::from(action == Action::Top);
            let single_dash = option.get(1) != Some(&b'-');
            if arg_count == 0 && single_dash && !value.is_empty() {
                // -hx: 값을 받지 않는 짧은 옵션 뒤의 글자를 다음 짧은 옵션으로 본다
                if sep_eq || value[0] == b'-' {
                    return Err(Stop::Usage("ignored explicit argument".into()));
                }
                pending.push((action, Vec::new()));
                option = vec![b'-', value[0]];
                let Some(next) = lookup(&option) else {
                    self.extras += 1;
                    break start + 1;
                };
                action = next;
                let rest = &value[1..];
                sep_eq = rest.first() == Some(&b'=');
                explicit = match rest {
                    [] => None,
                    [b'=', tail @ ..] => Some(tail.to_vec()),
                    _ => Some(rest.to_vec()),
                };
            } else if arg_count == 1 {
                pending.push((action, vec![value]));
                break start + 1;
            } else {
                return Err(Stop::Usage("ignored explicit argument".into()));
            }
        };
        for (action, values) in pending {
            self.take_action(action, &values)?;
        }
        Ok(stop)
    }

    /// argparse 의 consume_positionals (위치 인자는 file 하나)
    fn consume_positionals(&mut self, start: usize) -> usize {
        if self.file.is_some() {
            return start;
        }
        let Some(count) = match_one(&self.slots[start..]) else {
            return start;
        };
        // _get_values 가 첫 '--' 를 지운다. 남는 것은 'A' 하나다
        if let Some(i) = (start..start + count).find(|&i| matches!(self.slots[i], Slot::Arg)) {
            self.file = Some(self.raw[i].clone());
        }
        start + count
    }

    fn run(&mut self) -> Result<Args, Stop> {
        let option_indices: Vec<usize> = (0..self.slots.len())
            .filter(|&i| matches!(self.slots[i], Slot::Opt(_)))
            .collect();
        let mut start = 0;
        if let Some(&max_option) = option_indices.last() {
            while start <= max_option {
                let Some(&next_option) = option_indices.iter().find(|&&i| i >= start) else {
                    break;
                };
                if start != next_option {
                    let end = self.consume_positionals(start);
                    if end > start {
                        start = end;
                        continue;
                    }
                }
                if start != next_option {
                    self.extras += next_option - start;
                    start = next_option;
                }
                start = self.consume_optional(start)?;
            }
        }
        let stop = self.consume_positionals(start);
        self.extras += self.slots.len().saturating_sub(stop);
        let Some(file) = self.file.take() else {
            return Err(Stop::Usage(
                "the following arguments are required: file".into(),
            ));
        };
        if self.extras > 0 {
            return Err(Stop::Usage("unrecognized arguments".into()));
        }
        Ok(Args {
            file,
            top: self.top,
            json: self.json,
        })
    }
}

/// 프로그램 이름을 뺀 인자들을 해석한다
pub fn parse(raw: &[OsString]) -> Outcome {
    let argv: Vec<Cow<'_, [u8]>> = raw.iter().map(|a| arg_bytes(a)).collect();
    let mut slots = Vec::with_capacity(argv.len());
    let mut after_sep = false;
    for arg in &argv {
        if after_sep {
            slots.push(Slot::Arg);
        } else if arg.as_ref() == b"--" {
            after_sep = true;
            slots.push(Slot::Sep);
        } else {
            match parse_optional(arg) {
                Ok(Some(tuple)) => slots.push(Slot::Opt(tuple)),
                Ok(None) => slots.push(Slot::Arg),
                Err(Stop::Usage(msg)) => return Outcome::Usage(msg),
                Err(Stop::Help) => return Outcome::Help,
            }
        }
    }
    let mut parser = Parser {
        argv,
        raw,
        slots,
        file: None,
        top: 10,
        json: false,
        extras: 0,
    };
    match parser.run() {
        Ok(args) => Outcome::Run(args),
        Err(Stop::Help) => Outcome::Help,
        Err(Stop::Usage(msg)) => Outcome::Usage(msg),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(args: &[&str]) -> Outcome {
        let raw: Vec<OsString> = args.iter().map(OsString::from).collect();
        parse(&raw)
    }

    fn ok(file: &str, top: usize, json: bool) -> Outcome {
        Outcome::Run(Args {
            file: file.into(),
            top,
            json,
        })
    }

    fn is_usage(outcome: Outcome) -> bool {
        matches!(outcome, Outcome::Usage(_))
    }

    #[test]
    fn positive_int_rules() {
        assert_eq!(positive_int(b"007"), Ok(7));
        assert_eq!(
            positive_int(b"999999999999999999"),
            Ok(999_999_999_999_999_999)
        );
        assert_eq!(positive_int(b"1000000000000000000"), Ok(usize::MAX));
        assert_eq!(positive_int("9".repeat(5000).as_bytes()), Ok(usize::MAX));
        for bad in [
            "", "0", "000", "+3", " 3", "3 ", "-1", "1_0", "２", "٣", "abc",
        ] {
            assert!(positive_int(bad.as_bytes()).is_err(), "{bad:?}");
        }
        assert!(positive_int(b"\xff").is_err());
    }

    #[test]
    fn basic_forms() {
        assert_eq!(run(&["a.txt"]), ok("a.txt", 10, false));
        assert_eq!(
            run(&["a.txt", "--top", "2", "--json"]),
            ok("a.txt", 2, true)
        );
        assert_eq!(run(&["--json", "a.txt", "--top=3"]), ok("a.txt", 3, true));
        assert_eq!(
            run(&["a.txt", "--top", "1", "--top", "2"]),
            ok("a.txt", 2, false)
        );
        assert_eq!(run(&["-"]), ok("-", 10, false));
        assert_eq!(run(&["--", "a.txt"]), ok("a.txt", 10, false));
        assert_eq!(run(&["a.txt", "--"]), ok("a.txt", 10, false));
        assert_eq!(run(&["--", "-x"]), ok("-x", 10, false));
        assert_eq!(run(&["--", "--"]), ok("--", 10, false));
        assert_eq!(run(&["--json", "--", "-x"]), ok("-x", 10, true));
        assert_eq!(run(&["-5"]), ok("-5", 10, false));
        assert_eq!(run(&["-1.5"]), ok("-1.5", 10, false));
        assert_eq!(run(&["-.5"]), ok("-.5", 10, false));
        assert_eq!(run(&["-٣"]), ok("-٣", 10, false));
        assert_eq!(run(&["-5\n"]), ok("-5\n", 10, false));
        assert_eq!(run(&["-a b"]), ok("-a b", 10, false));
        assert_eq!(run(&[""]), ok("", 10, false));
    }

    #[test]
    fn abbreviations() {
        assert_eq!(run(&["a.txt", "--to", "2"]), ok("a.txt", 2, false));
        assert_eq!(run(&["a.txt", "--t=2"]), ok("a.txt", 2, false));
        assert_eq!(run(&["a.txt", "--js"]), ok("a.txt", 10, true));
        assert_eq!(run(&["a.txt", "--j"]), ok("a.txt", 10, true));
        assert_eq!(run(&["a.txt", "--h"]), Outcome::Help);
        assert!(is_usage(run(&["a.txt", "--=1"])));
    }

    #[test]
    fn help() {
        assert_eq!(run(&["-h"]), Outcome::Help);
        assert_eq!(run(&["--help"]), Outcome::Help);
        assert_eq!(run(&["-hx"]), Outcome::Help);
        assert_eq!(run(&["-hh"]), Outcome::Help);
        assert_eq!(run(&["--bogus", "-h"]), Outcome::Help);
        assert_eq!(run(&["a.txt", "b.txt", "-h"]), Outcome::Help);
        assert!(is_usage(run(&["-h=1"])));
        assert!(is_usage(run(&["-h-x"])));
        assert!(is_usage(run(&["-hh=x"])));
        assert!(is_usage(run(&["--help=1"])));
        assert!(is_usage(run(&["--top", "0", "-h"])));
        assert!(is_usage(run(&["--=1", "-h"])));
    }

    #[test]
    fn usage_errors() {
        assert!(is_usage(run(&[])));
        assert!(is_usage(run(&["--json"])));
        assert!(is_usage(run(&["a.txt", "b.txt"])));
        assert!(is_usage(run(&["a.txt", "--bogus"])));
        assert!(is_usage(run(&["a.txt", "-x.txt"])));
        assert!(is_usage(run(&["-1."])));
        assert!(is_usage(run(&["a.txt", "--json=1"])));
        assert!(is_usage(run(&["a.txt", "--json="])));
        assert!(is_usage(run(&["a.txt", "--top"])));
        assert!(is_usage(run(&["a.txt", "--top", "--json"])));
        assert!(is_usage(run(&["a.txt", "--top="])));
        assert!(is_usage(run(&["a.txt", "--top", "0", "--top", "2"])));
        assert!(is_usage(run(&["a.txt", "--top", "-1"])));
        assert!(is_usage(run(&["a.txt", "--top", "3", "--"])));
        assert!(is_usage(run(&["--top", "--", "3", "a.txt"])));
        assert!(is_usage(run(&["--", "--", "a.txt"])));
    }

    #[test]
    fn non_utf8_arguments() {
        #[cfg(unix)]
        {
            use std::os::unix::ffi::OsStringExt;
            let raw = vec![OsString::from_vec(b"gone\xff.txt".to_vec())];
            match parse(&raw) {
                Outcome::Run(args) => assert_eq!(display_name(&args.file), "gone\u{fffd}.txt"),
                other => panic!("{other:?}"),
            }
            let name = OsString::from_vec(b"x\xe2\x82y\xf0\x9f.txt".to_vec());
            assert_eq!(display_name(&name), "x\u{fffd}y\u{fffd}.txt");
            let raw: Vec<OsString> = vec![
                "a.txt".into(),
                "--top".into(),
                OsString::from_vec(vec![0xff]),
            ];
            assert!(is_usage(parse(&raw)));
        }
    }
}
