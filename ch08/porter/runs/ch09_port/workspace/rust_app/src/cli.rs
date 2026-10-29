//! `argparse.ArgumentParser(allow_abbrev=False)` 의 분류·소비 규칙 중 이 프로그램에 필요한 부분(Python 3.12).
//!
//! - 이름이 정확히 같은 옵션만 받는다. `--top=3` 처럼 `=값` 을 붙일 수 있다
//! - 같은 옵션을 반복하면 마지막 값(값마다 검증한다)
//! - 처음 나온 `--` 뒤는 모두 위치 인자, `-` 단독·음수 모양(`-5`, `-.5`)·공백이 든 문자열은 위치 인자
//! - 왼쪽부터 처리하다가 값 오류가 나면 바로 오류, `-h`/`--help` 를 만나면 바로 도움말.
//!   알 수 없는 옵션·남는 인자·FILE 누락은 끝까지 본 뒤 오류

use std::ffi::OsString;

use crate::Format;

/// 인자 오류 때 stderr 에 쓰는 사용법(계약상 비교 안 함, 80열 기준으로 고정). 도움말은 help.rs
pub const USAGE: &str = "usage: logstat [-h] [--format {csv,jsonl}] [--top TOP] [--json] [--strict]
               file
";

/// re 의 `\d`(str 패턴)가 받는 코드 포인트(Unicode 10진 숫자). verify/decimal_ranges.py 로 Python 3.12.3 에서 뽑았다.
const DECIMAL_RANGES: [(u32, u32); 64] = [
    (0x30, 0x39),
    (0x660, 0x669),
    (0x6F0, 0x6F9),
    (0x7C0, 0x7C9),
    (0x966, 0x96F),
    (0x9E6, 0x9EF),
    (0xA66, 0xA6F),
    (0xAE6, 0xAEF),
    (0xB66, 0xB6F),
    (0xBE6, 0xBEF),
    (0xC66, 0xC6F),
    (0xCE6, 0xCEF),
    (0xD66, 0xD6F),
    (0xDE6, 0xDEF),
    (0xE50, 0xE59),
    (0xED0, 0xED9),
    (0xF20, 0xF29),
    (0x1040, 0x1049),
    (0x1090, 0x1099),
    (0x17E0, 0x17E9),
    (0x1810, 0x1819),
    (0x1946, 0x194F),
    (0x19D0, 0x19D9),
    (0x1A80, 0x1A89),
    (0x1A90, 0x1A99),
    (0x1B50, 0x1B59),
    (0x1BB0, 0x1BB9),
    (0x1C40, 0x1C49),
    (0x1C50, 0x1C59),
    (0xA620, 0xA629),
    (0xA8D0, 0xA8D9),
    (0xA900, 0xA909),
    (0xA9D0, 0xA9D9),
    (0xA9F0, 0xA9F9),
    (0xAA50, 0xAA59),
    (0xABF0, 0xABF9),
    (0xFF10, 0xFF19),
    (0x104A0, 0x104A9),
    (0x10D30, 0x10D39),
    (0x11066, 0x1106F),
    (0x110F0, 0x110F9),
    (0x11136, 0x1113F),
    (0x111D0, 0x111D9),
    (0x112F0, 0x112F9),
    (0x11450, 0x11459),
    (0x114D0, 0x114D9),
    (0x11650, 0x11659),
    (0x116C0, 0x116C9),
    (0x11730, 0x11739),
    (0x118E0, 0x118E9),
    (0x11950, 0x11959),
    (0x11C50, 0x11C59),
    (0x11D50, 0x11D59),
    (0x11DA0, 0x11DA9),
    (0x11F50, 0x11F59),
    (0x16A60, 0x16A69),
    (0x16AC0, 0x16AC9),
    (0x16B50, 0x16B59),
    (0x1D7CE, 0x1D7FF),
    (0x1E140, 0x1E149),
    (0x1E2F0, 0x1E2F9),
    (0x1E4F0, 0x1E4F9),
    (0x1E950, 0x1E959),
    (0x1FBF0, 0x1FBF9),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Action {
    Help,
    Format,
    Top,
    Json,
    Strict,
}

impl Action {
    fn takes_value(self) -> bool {
        matches!(self, Action::Format | Action::Top)
    }
}

fn action_for(name: &str) -> Option<Action> {
    match name {
        "-h" | "--help" => Some(Action::Help),
        "--format" => Some(Action::Format),
        "--top" => Some(Action::Top),
        "--json" => Some(Action::Json),
        "--strict" => Some(Action::Strict),
        _ => None,
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct Args {
    pub file: OsString,
    pub format: Option<Format>,
    pub top: u64,
    pub json: bool,
    pub strict: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Outcome {
    Run(Args),
    /// 도움말을 stdout 에 쓰고 종료 0
    Help,
    /// 인자 오류, 종료 2
    Error(String),
}

/// `_parse_optional` 의 결과 중 옵션인 경우
#[derive(Debug, Clone)]
struct OptTuple {
    /// None 이면 알 수 없는 옵션
    action: Option<Action>,
    option: String,
    /// `=` 로 나뉘었는가
    sep: bool,
    explicit: Option<String>,
}

fn is_decimal(c: char) -> bool {
    decimal_value(c).is_some()
}

/// `Py_UNICODE_TODECIMAL`. 모든 10진 숫자 블록은 0부터 시작하는 10자 묶음이다(verify/int_charsets.py)
pub(crate) fn decimal_value(c: char) -> Option<u32> {
    let c = c as u32;
    DECIMAL_RANGES
        .iter()
        .find(|&&(a, b)| (a..=b).contains(&c))
        .map(|&(a, _)| (c - a) % 10)
}

/// `^-\d+$|^-\d*\.\d+$` (`$` 는 끝의 개행 하나 앞에서도 맞는다)
fn looks_negative(arg: &str) -> bool {
    let Some(body) = arg.strip_prefix('-') else {
        return false;
    };
    let body = body.strip_suffix('\n').unwrap_or(body);
    let digits = |s: &str| !s.is_empty() && s.chars().all(is_decimal);
    match body.split_once('.') {
        None => digits(body),
        Some((int, frac)) => (int.is_empty() || int.chars().all(is_decimal)) && digits(frac),
    }
}

/// None 이면 위치 인자
fn classify(arg: &str) -> Option<OptTuple> {
    if !arg.starts_with('-') {
        return None;
    }
    if let Some(action) = action_for(arg) {
        return Some(OptTuple {
            action: Some(action),
            option: arg.to_string(),
            sep: false,
            explicit: None,
        });
    }
    if arg.chars().count() == 1 {
        return None;
    }
    if let Some((name, value)) = arg.split_once('=') {
        if let Some(action) = action_for(name) {
            return Some(OptTuple {
                action: Some(action),
                option: name.to_string(),
                sep: true,
                explicit: Some(value.to_string()),
            });
        }
    }
    // allow_abbrev=False 라도 한 글자 옵션(-h) 뒤에 붙은 글자는 나눠 본다
    if !arg.starts_with("--") {
        if let Some(rest) = arg.strip_prefix("-h") {
            return Some(OptTuple {
                action: Some(Action::Help),
                option: "-h".to_string(),
                sep: false,
                explicit: Some(rest.to_string()),
            });
        }
    }
    if looks_negative(arg) || arg.contains(' ') {
        return None;
    }
    Some(OptTuple {
        action: None,
        option: arg.to_string(),
        sep: false,
        explicit: None,
    })
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Pattern {
    /// 인자
    A,
    /// 옵션
    O,
    /// 처음 나온 `--`
    DashDash,
}

enum Stop {
    Help,
    Error(String),
}

fn positive_int(value: &str) -> Result<u64, String> {
    // int() 는 4300자리(앞의 0 포함)가 넘으면 ValueError
    if value.is_empty()
        || !value.bytes().all(|b| b.is_ascii_digit())
        || value.len() > 4300
        || value.bytes().all(|b| b == b'0')
    {
        return Err(format!(
            "argument --top: invalid positive_int value: '{value}'"
        ));
    }
    Ok(value.parse::<u64>().unwrap_or(u64::MAX))
}

struct State<'a> {
    args: &'a [OsString],
    pattern: Vec<Pattern>,
    tuples: Vec<Option<OptTuple>>,
    file: Option<OsString>,
    format: Option<Format>,
    top: u64,
    json: bool,
    strict: bool,
    extras: bool,
}

impl State<'_> {
    fn take_action(&mut self, action: Action, value: Option<String>) -> Result<(), Stop> {
        let value = value.unwrap_or_default();
        match action {
            Action::Help => return Err(Stop::Help),
            Action::Format => {
                self.format = Some(match value.as_str() {
                    "csv" => Format::Csv,
                    "jsonl" => Format::Jsonl,
                    _ => {
                        let msg = format!("argument --format: invalid choice: '{value}'");
                        return Err(Stop::Error(msg));
                    }
                });
            }
            Action::Top => self.top = positive_int(&value).map_err(Stop::Error)?,
            Action::Json => self.json = true,
            Action::Strict => self.strict = true,
        }
        Ok(())
    }

    /// FILE(nargs=None, 패턴 `-*A-*`)을 아직 못 받았으면 start 부터 맞춰 본다.
    fn consume_positionals(&mut self, start: usize) -> usize {
        if self.file.is_some() {
            return start;
        }
        let mut j = start;
        while self.pattern.get(j) == Some(&Pattern::DashDash) {
            j += 1;
        }
        if self.pattern.get(j) != Some(&Pattern::A) {
            return start;
        }
        j += 1;
        while self.pattern.get(j) == Some(&Pattern::DashDash) {
            j += 1;
        }
        // 위치 인자의 값에서는 처음 나온 '--' 하나를 뺀다
        let mut values: Vec<&OsString> = self.args[start..j].iter().collect();
        if let Some(i) = values.iter().position(|v| v.as_os_str() == "--") {
            values.remove(i);
        }
        self.file = values.first().map(|v| (*v).clone());
        j
    }

    fn consume_optional(&mut self, start: usize) -> Result<usize, Stop> {
        let Some(mut t) = self.tuples[start].clone() else {
            return Ok(start + 1);
        };
        let mut actions: Vec<(Action, Option<String>)> = Vec::new();
        let stop;
        loop {
            let Some(action) = t.action else {
                self.extras = true;
                return Ok(start + 1);
            };
            match t.explicit.clone() {
                Some(explicit) => {
                    let single_dash = !t.option.starts_with("--");
                    if !action.takes_value() && single_dash && !explicit.is_empty() {
                        if t.sep || explicit.starts_with('-') {
                            return Err(Stop::Error(format!(
                                "ignored explicit argument '{explicit}'"
                            )));
                        }
                        actions.push((action, None));
                        let first = explicit.chars().next().unwrap_or('-');
                        let option = format!("-{first}");
                        match action_for(&option) {
                            Some(next) => {
                                let rest = &explicit[first.len_utf8()..];
                                t = OptTuple {
                                    action: Some(next),
                                    option,
                                    sep: rest.starts_with('='),
                                    explicit: if rest.is_empty() {
                                        None
                                    } else {
                                        Some(rest.strip_prefix('=').unwrap_or(rest).to_string())
                                    },
                                };
                            }
                            None => {
                                self.extras = true;
                                stop = start + 1;
                                break;
                            }
                        }
                    } else if action.takes_value() {
                        actions.push((action, Some(explicit)));
                        stop = start + 1;
                        break;
                    } else {
                        return Err(Stop::Error(format!(
                            "ignored explicit argument '{explicit}'"
                        )));
                    }
                }
                None => {
                    if action.takes_value() {
                        if self.pattern.get(start + 1) != Some(&Pattern::A) {
                            return Err(Stop::Error(format!(
                                "argument {}: expected one argument",
                                t.option
                            )));
                        }
                        let value = self.args[start + 1].to_string_lossy().into_owned();
                        actions.push((action, Some(value)));
                        stop = start + 2;
                    } else {
                        actions.push((action, None));
                        stop = start + 1;
                    }
                    break;
                }
            }
        }
        for (action, value) in actions {
            self.take_action(action, value)?;
        }
        Ok(stop)
    }

    fn parse(&mut self) -> Result<(), Stop> {
        let option_indices: Vec<usize> = (0..self.args.len())
            .filter(|&i| self.pattern[i] == Pattern::O)
            .collect();
        let mut start = 0;
        if let Some(&max_option) = option_indices.last() {
            while start <= max_option {
                let next_option = option_indices
                    .iter()
                    .copied()
                    .find(|&i| i >= start)
                    .unwrap_or(max_option);
                if start != next_option {
                    let end = self.consume_positionals(start);
                    if end > start {
                        start = end;
                        continue;
                    }
                }
                if self.pattern[start] != Pattern::O {
                    self.extras = true;
                    start = next_option;
                }
                start = self.consume_optional(start)?;
            }
        }
        let stop = self.consume_positionals(start);
        if stop < self.args.len() {
            self.extras = true;
        }
        if self.file.is_none() {
            return Err(Stop::Error(
                "the following arguments are required: file".to_string(),
            ));
        }
        if self.extras {
            return Err(Stop::Error("unrecognized arguments".to_string()));
        }
        Ok(())
    }
}

pub fn parse(args: &[OsString]) -> Outcome {
    let mut pattern = Vec::with_capacity(args.len());
    let mut tuples = Vec::with_capacity(args.len());
    let mut after_dashdash = false;
    for arg in args {
        if after_dashdash {
            pattern.push(Pattern::A);
            tuples.push(None);
        } else if arg.as_os_str() == "--" {
            after_dashdash = true;
            pattern.push(Pattern::DashDash);
            tuples.push(None);
        } else {
            let tuple = classify(&arg.to_string_lossy());
            pattern.push(if tuple.is_some() {
                Pattern::O
            } else {
                Pattern::A
            });
            tuples.push(tuple);
        }
    }
    let mut state = State {
        args,
        pattern,
        tuples,
        file: None,
        format: None,
        top: 10,
        json: false,
        strict: false,
        extras: false,
    };
    match state.parse() {
        Err(Stop::Help) => Outcome::Help,
        Err(Stop::Error(msg)) => Outcome::Error(msg),
        Ok(()) => Outcome::Run(Args {
            file: state.file.unwrap_or_default(),
            format: state.format,
            top: state.top,
            json: state.json,
            strict: state.strict,
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(args: &[&str]) -> Outcome {
        let args: Vec<OsString> = args.iter().map(OsString::from).collect();
        parse(&args)
    }

    fn run_args(file: &str, format: Option<Format>, top: u64, json: bool, strict: bool) -> Outcome {
        Outcome::Run(Args {
            file: file.into(),
            format,
            top,
            json,
            strict,
        })
    }

    fn is_error(o: Outcome) -> bool {
        matches!(o, Outcome::Error(_))
    }

    #[test]
    fn accepted_forms() {
        assert_eq!(p(&["a.csv"]), run_args("a.csv", None, 10, false, false));
        assert_eq!(
            p(&["--json", "--json", "a.csv"]),
            run_args("a.csv", None, 10, true, false)
        );
        assert_eq!(
            p(&["a", "--format", "csv", "--format", "jsonl"]),
            run_args("a", Some(Format::Jsonl), 10, false, false)
        );
        assert_eq!(
            p(&["--top=3", "a.csv"]),
            run_args("a.csv", None, 3, false, false)
        );
        assert_eq!(
            p(&["a.csv", "--top", "007"]),
            run_args("a.csv", None, 7, false, false)
        );
        assert_eq!(
            p(&["a.csv", "--top", "99999999999999999999999"]),
            run_args("a.csv", None, u64::MAX, false, false)
        );
        assert_eq!(
            p(&["--", "-x.csv"]),
            run_args("-x.csv", None, 10, false, false)
        );
        assert_eq!(
            p(&["a.csv", "--"]),
            run_args("a.csv", None, 10, false, false)
        );
        assert_eq!(p(&["--", "--"]), run_args("--", None, 10, false, false));
        assert_eq!(
            p(&["-5", "--strict"]),
            run_args("-5", None, 10, false, true)
        );
        assert_eq!(p(&["-", "--strict"]), run_args("-", None, 10, false, true));
        assert_eq!(p(&["-a b"]), run_args("-a b", None, 10, false, false));
        assert_eq!(p(&["-٣"]), run_args("-٣", None, 10, false, false));
        assert_eq!(p(&[""]), run_args("", None, 10, false, false));
    }

    #[test]
    fn errors_and_help() {
        assert!(is_error(p(&[])));
        assert!(is_error(p(&["a.csv", "--js"])));
        assert!(is_error(p(&["a.csv", "--top", "0"])));
        assert!(is_error(p(&["a.csv", "--top", "-5"])));
        assert!(is_error(p(&["a.csv", "--top", "٣"])));
        assert!(is_error(p(&["a.csv", "--top", &"1".repeat(4301)])));
        assert!(is_error(p(&["a.csv", "--top"])));
        assert!(is_error(p(&["a.csv", "--top="])));
        assert!(is_error(p(&["a.csv", "--format", "tsv"])));
        assert!(is_error(p(&["a.csv", "--format", "--json"])));
        assert!(is_error(p(&["a.csv", "--json=1"])));
        assert!(is_error(p(&["a.csv", "b.csv"])));
        assert!(is_error(p(&["--", "a.csv", "--json"])));
        assert!(is_error(p(&["a.csv", "-x"])));
        assert!(is_error(p(&["a.csv", "-h=1"])));
        assert!(is_error(p(&["a.csv", "--top", "0", "--help"])));
        assert_eq!(p(&["a.csv", "--help", "--top", "0"]), Outcome::Help);
        assert_eq!(p(&["--js", "-h"]), Outcome::Help);
        assert_eq!(p(&["-hx"]), Outcome::Help);
        assert_eq!(
            p(&[]),
            Outcome::Error("the following arguments are required: file".into())
        );
    }
}
