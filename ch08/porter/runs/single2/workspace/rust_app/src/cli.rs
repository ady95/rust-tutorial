//! 명령행(계약 1절). 기준 구현이 쓰는 Python 3.12 argparse 의 해석 순서를 그대로 따른다
//! (_parse_known_args, _parse_optional, _get_option_tuples, consume_optional, consume_positionals).
//! 접두어 약어(--to, --js), --top 반복 시 마지막 값, '--' 처리, 음수 모양 위치 인자가 여기에 들어 있다.

use std::ffi::OsString;

use crate::text::is_decimal;

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

const DEFAULT_TOP: usize = 10;

/// --top 이 이보다 큰 자릿수면 그냥 "아주 큰 수"로 본다 (기준 구현의 MAX_TOP_DIGITS)
const MAX_TOP_DIGITS: usize = 18;

#[derive(Debug, PartialEq, Eq)]
pub struct Args {
    pub file: OsString,
    pub top: usize,
    pub json: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Command {
    Run(Args),
    Help,
}

/// 인자 오류. 메시지 내용은 계약상 비교하지 않는다.
#[derive(Debug, PartialEq, Eq)]
pub struct UsageError(pub String);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Action {
    Help,
    Top,
    Json,
}

impl Action {
    /// 이 옵션이 받는 값의 수 (help·json 은 0, top 은 1)
    fn nargs(self) -> usize {
        match self {
            Action::Top => 1,
            Action::Help | Action::Json => 0,
        }
    }
}

/// argparse 에 등록된 순서대로
const OPTIONS: [(&str, Action); 4] = [
    ("-h", Action::Help),
    ("--help", Action::Help),
    ("--top", Action::Top),
    ("--json", Action::Json),
];

fn lookup(option: &str) -> Option<Action> {
    OPTIONS
        .iter()
        .find(|(name, _)| *name == option)
        .map(|&(_, action)| action)
}

/// argparse 의 sep: None, '' (붙여 쓴 짧은 옵션), '='
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Sep {
    None,
    Empty,
    Equals,
}

#[derive(Debug, Clone)]
struct OptionTuple {
    action: Option<Action>,
    option_string: String,
    sep: Sep,
    explicit_arg: Option<String>,
}

impl OptionTuple {
    fn new(action: Option<Action>, option_string: &str, sep: Sep, explicit: Option<&str>) -> Self {
        OptionTuple {
            action,
            option_string: option_string.to_string(),
            sep,
            explicit_arg: explicit.map(str::to_string),
        }
    }
}

/// '^-\d+$|^-\d*\.\d+$' (Python re: $ 는 끝의 '\n' 하나 앞에서도 맞는다)
fn looks_like_negative_number(arg: &str) -> bool {
    let Some(rest) = arg.strip_prefix('-') else {
        return false;
    };
    let body = rest.strip_suffix('\n').unwrap_or(rest);
    let all_digits = |s: &str| s.chars().all(is_decimal);
    match body.split_once('.') {
        None => !body.is_empty() && all_digits(body),
        Some((int, frac)) => all_digits(int) && !frac.is_empty() && all_digits(frac),
    }
}

fn get_option_tuples(arg: &str) -> Vec<OptionTuple> {
    let mut result = Vec::new();
    if arg.starts_with("--") {
        let (prefix, sep, explicit) = match arg.split_once('=') {
            Some((prefix, explicit)) => (prefix, Sep::Equals, Some(explicit)),
            None => (arg, Sep::None, None),
        };
        for &(name, action) in &OPTIONS {
            if name.starts_with(prefix) {
                result.push(OptionTuple::new(Some(action), name, sep, explicit));
            }
        }
    } else {
        // 앞의 두 글자('-' 와 그 다음 글자)가 짧은 옵션, 나머지는 붙여 쓴 값
        let split = arg.char_indices().nth(2).map_or(arg.len(), |(i, _)| i);
        let (short, short_explicit) = arg.split_at(split);
        for &(name, action) in &OPTIONS {
            if name == short {
                result.push(OptionTuple::new(
                    Some(action),
                    name,
                    Sep::Empty,
                    Some(short_explicit),
                ));
            } else if name.starts_with(arg) {
                result.push(OptionTuple::new(Some(action), name, Sep::None, None));
            }
        }
    }
    result
}

/// None 이면 위치 인자
fn parse_optional(arg: &str) -> Result<Option<OptionTuple>, UsageError> {
    if !arg.starts_with('-') {
        return Ok(None);
    }
    if let Some(action) = lookup(arg) {
        return Ok(Some(OptionTuple::new(Some(action), arg, Sep::None, None)));
    }
    if arg.chars().count() == 1 {
        return Ok(None);
    }
    if let Some((option, explicit)) = arg.split_once('=') {
        if let Some(action) = lookup(option) {
            return Ok(Some(OptionTuple::new(
                Some(action),
                option,
                Sep::Equals,
                Some(explicit),
            )));
        }
    }
    let mut tuples = get_option_tuples(arg);
    if tuples.len() > 1 {
        let names: Vec<&str> = tuples.iter().map(|t| t.option_string.as_str()).collect();
        return Err(UsageError(format!(
            "ambiguous option: {arg} could match {}",
            names.join(", ")
        )));
    }
    if let Some(tuple) = tuples.pop() {
        return Ok(Some(tuple));
    }
    if looks_like_negative_number(arg) || arg.contains(' ') {
        return Ok(None);
    }
    Ok(Some(OptionTuple::new(None, arg, Sep::None, None)))
}

/// 계약 1절: ASCII 숫자만. 앞의 0 은 무시, 0 은 오류, 18자리를 넘으면 아주 큰 수
fn positive_int(value: &str) -> Result<usize, UsageError> {
    if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(UsageError(format!(
            "argument --top: not an integer: {value}"
        )));
    }
    let digits = value.trim_start_matches('0');
    if digits.is_empty() {
        return Err(UsageError(format!(
            "argument --top: must be at least 1: {value}"
        )));
    }
    if digits.len() > MAX_TOP_DIGITS {
        return Ok(usize::MAX);
    }
    let n = digits
        .bytes()
        .fold(0u64, |acc, b| acc * 10 + u64::from(b - b'0'));
    Ok(usize::try_from(n).unwrap_or(usize::MAX))
}

struct Parser<'a> {
    raw: &'a [OsString],
    strings: Vec<String>,
    pattern: Vec<u8>,
    options: Vec<Option<OptionTuple>>,
    file: Option<OsString>,
    file_pending: bool,
    top: usize,
    json: bool,
    extras: Vec<String>,
}

/// 옵션 처리 결과: 다음 위치, 또는 도움말 출력
enum Step {
    Next(usize),
    Help,
}

impl Parser<'_> {
    /// 위치 인자 file 의 패턴 '(-*A-*)' 를 start 에서 맞춰 본다
    fn consume_positionals(&mut self, start: usize) -> usize {
        if !self.file_pending {
            return start;
        }
        let rest = &self.pattern[start..];
        let leading = rest.iter().take_while(|&&p| p == b'-').count();
        if rest.get(leading) != Some(&b'A') {
            return start;
        }
        let trailing = rest[leading + 1..]
            .iter()
            .take_while(|&&p| p == b'-')
            .count();
        let end = start + leading + 1 + trailing;
        // 첫 '--' 하나를 빼면 값 하나가 남는다
        let mut values: Vec<usize> = (start..end).collect();
        if let Some(pos) = values.iter().position(|&i| self.strings[i] == "--") {
            values.remove(pos);
        }
        if let Some(&i) = values.first() {
            self.file = Some(self.raw[i].clone());
        }
        self.file_pending = false;
        end
    }

    fn take_action(
        &mut self,
        action: Action,
        value: Option<&str>,
    ) -> Result<Option<Step>, UsageError> {
        match action {
            Action::Help => return Ok(Some(Step::Help)),
            Action::Json => self.json = true,
            Action::Top => self.top = positive_int(value.unwrap_or_default())?,
        }
        Ok(None)
    }

    fn consume_optional(&mut self, start: usize) -> Result<Step, UsageError> {
        let Some(tuple) = self.options[start].clone() else {
            return Ok(Step::Next(start + 1));
        };
        let OptionTuple {
            action,
            mut option_string,
            mut sep,
            mut explicit_arg,
        } = tuple;
        let mut action = action;
        let mut actions: Vec<(Action, Option<String>)> = Vec::new();
        let stop;
        loop {
            let Some(act) = action else {
                self.extras.push(self.strings[start].clone());
                return Ok(Step::Next(start + 1));
            };
            if let Some(explicit) = explicit_arg.take() {
                let short = !option_string[1..].starts_with('-');
                if act.nargs() == 0 && short && !explicit.is_empty() {
                    if sep == Sep::Equals || explicit.starts_with('-') {
                        return Err(UsageError(format!(
                            "argument {option_string}: ignored explicit argument '{explicit}'"
                        )));
                    }
                    actions.push((act, None));
                    let mut chars = explicit.chars();
                    let first = chars.next().unwrap_or_default();
                    let rest = chars.as_str();
                    option_string = format!("-{first}");
                    if let Some(next) = lookup(&option_string) {
                        action = Some(next);
                        if rest.is_empty() {
                            sep = Sep::None;
                            explicit_arg = None;
                        } else if let Some(after) = rest.strip_prefix('=') {
                            sep = Sep::Equals;
                            explicit_arg = Some(after.to_string());
                        } else {
                            sep = Sep::Empty;
                            explicit_arg = Some(rest.to_string());
                        }
                    } else {
                        self.extras.push(format!("-{explicit}"));
                        stop = start + 1;
                        break;
                    }
                } else if act.nargs() == 1 {
                    actions.push((act, Some(explicit)));
                    stop = start + 1;
                    break;
                } else {
                    return Err(UsageError(format!(
                        "argument {option_string}: ignored explicit argument '{explicit}'"
                    )));
                }
            } else {
                let next = start + 1;
                let mut value = None;
                if act.nargs() == 1 {
                    if self.pattern.get(next) != Some(&b'A') {
                        return Err(UsageError(format!(
                            "argument {option_string}: expected one argument"
                        )));
                    }
                    value = Some(self.strings[next].clone());
                }
                actions.push((act, value));
                stop = next + act.nargs();
                break;
            }
        }
        for (act, value) in actions {
            if let Some(step) = self.take_action(act, value.as_deref())? {
                return Ok(step);
            }
        }
        Ok(Step::Next(stop))
    }

    fn run(&mut self) -> Result<Step, UsageError> {
        let option_indices: Vec<usize> = (0..self.options.len())
            .filter(|&i| self.pattern[i] == b'O')
            .collect();
        let mut start = 0;
        while let Some(&next) = option_indices.iter().find(|&&i| i >= start) {
            if start != next {
                let end = self.consume_positionals(start);
                if end > start {
                    start = end;
                    continue;
                }
            }
            if start != next {
                self.extras.extend_from_slice(&self.strings[start..next]);
                start = next;
            }
            match self.consume_optional(start)? {
                Step::Next(stop) => start = stop,
                Step::Help => return Ok(Step::Help),
            }
        }
        let stop = self.consume_positionals(start);
        self.extras.extend_from_slice(&self.strings[stop..]);
        Ok(Step::Next(stop))
    }
}

/// args 는 프로그램 이름을 뺀 인자들
pub fn parse(args: &[OsString]) -> Result<Command, UsageError> {
    // 옵션 판단과 오류 메시지에는 손실 변환한 문자열을 쓰고, 파일 이름은 원래 바이트를 그대로 쓴다
    let strings: Vec<String> = args
        .iter()
        .map(|a| a.to_string_lossy().into_owned())
        .collect();
    let mut pattern = Vec::with_capacity(strings.len());
    let mut options = Vec::with_capacity(strings.len());
    let mut after_double_dash = false;
    for arg in &strings {
        if after_double_dash {
            pattern.push(b'A');
            options.push(None);
        } else if arg == "--" {
            after_double_dash = true;
            pattern.push(b'-');
            options.push(None);
        } else {
            let tuple = parse_optional(arg)?;
            pattern.push(if tuple.is_some() { b'O' } else { b'A' });
            options.push(tuple);
        }
    }
    let mut parser = Parser {
        raw: args,
        strings,
        pattern,
        options,
        file: None,
        file_pending: true,
        top: DEFAULT_TOP,
        json: false,
        extras: Vec::new(),
    };
    if let Step::Help = parser.run()? {
        return Ok(Command::Help);
    }
    let Some(file) = parser.file else {
        return Err(UsageError(
            "the following arguments are required: file".to_string(),
        ));
    };
    if !parser.extras.is_empty() {
        return Err(UsageError(format!(
            "unrecognized arguments: {}",
            parser.extras.join(" ")
        )));
    }
    Ok(Command::Run(Args {
        file,
        top: parser.top,
        json: parser.json,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_strs(args: &[&str]) -> Result<Command, UsageError> {
        let args: Vec<OsString> = args.iter().map(OsString::from).collect();
        parse(&args)
    }

    fn run(file: &str, top: usize, json: bool) -> Result<Command, UsageError> {
        Ok(Command::Run(Args {
            file: OsString::from(file),
            top,
            json,
        }))
    }

    #[test]
    fn basic_forms() {
        assert_eq!(parse_strs(&["a.txt"]), run("a.txt", 10, false));
        assert_eq!(
            parse_strs(&["--top", "3", "a.txt", "--json"]),
            run("a.txt", 3, true)
        );
        assert_eq!(parse_strs(&["a.txt", "--top=1"]), run("a.txt", 1, false));
        assert_eq!(
            parse_strs(&["a.txt", "--to", "2", "--js"]),
            run("a.txt", 2, true)
        );
        assert_eq!(parse_strs(&["a.txt", "--t=2"]), run("a.txt", 2, false));
        assert!(parse_strs(&["a.txt", "--top", "0", "--top", "2"]).is_err());
        assert_eq!(
            parse_strs(&["a.txt", "--top", "1", "--top", "2"]),
            run("a.txt", 2, false)
        );
    }

    #[test]
    fn positional_edge_cases() {
        assert_eq!(parse_strs(&["-"]), run("-", 10, false));
        assert_eq!(parse_strs(&["--", "-x"]), run("-x", 10, false));
        assert_eq!(parse_strs(&["--", "--"]), run("--", 10, false));
        assert_eq!(parse_strs(&["a.txt", "--"]), run("a.txt", 10, false));
        assert_eq!(parse_strs(&["-5"]), run("-5", 10, false));
        assert_eq!(parse_strs(&["-.5"]), run("-.5", 10, false));
        assert_eq!(parse_strs(&["-5\n"]), run("-5\n", 10, false));
        assert_eq!(parse_strs(&["-x y"]), run("-x y", 10, false));
        assert_eq!(parse_strs(&[""]), run("", 10, false));
        assert!(parse_strs(&["a.txt", "--json", "--"]).is_err());
        assert!(parse_strs(&["a.txt", "b.txt"]).is_err());
        assert!(parse_strs(&["-x.txt"]).is_err());
        assert!(parse_strs(&[]).is_err());
        assert!(parse_strs(&["--"]).is_err());
    }

    #[test]
    fn help_and_errors() {
        assert_eq!(parse_strs(&["-h"]), Ok(Command::Help));
        assert_eq!(parse_strs(&["--he"]), Ok(Command::Help));
        assert_eq!(parse_strs(&["-hx"]), Ok(Command::Help));
        assert_eq!(parse_strs(&["--bogus", "-h"]), Ok(Command::Help));
        assert!(parse_strs(&["-h="]).is_err());
        assert!(parse_strs(&["--top", "0", "-h"]).is_err());
        assert!(parse_strs(&["-h", "--=x"]).is_err());
        assert!(parse_strs(&["a.txt", "--json=1"]).is_err());
        assert!(parse_strs(&["a.txt", "--top"]).is_err());
        assert!(parse_strs(&["a.txt", "--top", "--json"]).is_err());
    }

    #[test]
    fn top_values() {
        assert_eq!(positive_int("007"), Ok(7));
        assert_eq!(
            positive_int("999999999999999999"),
            Ok(999_999_999_999_999_999)
        );
        assert_eq!(positive_int("1000000000000000000"), Ok(usize::MAX));
        assert_eq!(positive_int(&"9".repeat(5000)), Ok(usize::MAX));
        for bad in [
            "", "0", "000", "+3", " 3", "3 ", "1_0", "２", "٣", "-1", "abc",
        ] {
            assert!(positive_int(bad).is_err(), "{bad:?}");
        }
    }
}
