//! 인자 해석: Python 3.12 argparse(allow_abbrev=False)의 동작을 이 프로그램의 인자 정의에 한해 그대로 따른다.
//!
//! 인자마다 종류를 정한 다음(`O` 옵션, `A` 인자, `-` 는 `--` 표시) argparse 와 같은 순서로 소비한다.
//! 오류와 `-h` 는 만나는 순서대로 처리하고, 남는 인자(extras)는 끝에서 오류가 된다.

use crate::pystr;

pub const USAGE: &str = "usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [file]";

pub const HELP: &str = "usage: mdtoc [-h] [--min-level N] [--max-level N] [--json] [file]

Make a table of contents from Markdown headings.

positional arguments:
  file             Markdown file (default: standard input)

options:
  -h, --help       show this help message and exit
  --min-level N
  --max-level N
  --json           print headings as JSON
";

pub struct Options {
    /// 파일 이름 바이트. `-` 는 표준 입력.
    pub file: Vec<u8>,
    pub min_level: u8,
    pub max_level: u8,
    pub json: bool,
}

pub enum Parsed {
    Run(Options),
    Help,
    /// 사용법 오류의 메시지(`mdtoc: error: ` 뒤에 붙는 부분)
    Usage(String),
}

#[derive(Clone, Copy, PartialEq)]
enum Act {
    Help,
    Min,
    Max,
    Json,
}

const OPTIONS: [(&str, Act); 5] = [
    ("-h", Act::Help),
    ("--help", Act::Help),
    ("--min-level", Act::Min),
    ("--max-level", Act::Max),
    ("--json", Act::Json),
];

fn act_of(name: &str) -> Option<Act> {
    OPTIONS.iter().find(|(n, _)| *n == name).map(|&(_, a)| a)
}

enum Kind<'a> {
    /// `--`
    Marker,
    Positional,
    /// 알려진 옵션(이름, 붙은 값). 값의 첫 항목은 `=` 로 붙었는지(argparse 의 sep)
    Opt(&'static str, Option<(bool, &'a [u8])>),
    /// 알 수 없는 옵션
    Unknown,
}

/// 정규식 `^-\d+$|^-\d*\.\d+$` (`$` 는 끝의 `\n` 하나도 허용). 이 인자 정의에는 음수 모양 옵션이 없다.
fn negative_number(arg: &[u8]) -> bool {
    let Ok(s) = std::str::from_utf8(arg) else {
        return false;
    };
    let s = s.strip_suffix('\n').unwrap_or(s);
    let Some(rest) = s.strip_prefix('-') else {
        return false;
    };
    let digits = |t: &str| t.chars().all(|c| pystr::decimal_value(c).is_some());
    if !rest.is_empty() && digits(rest) {
        return true;
    }
    rest.split_once('.')
        .is_some_and(|(a, b)| digits(a) && !b.is_empty() && digits(b))
}

/// argparse 의 `_parse_optional`.
fn parse_optional(arg: &[u8]) -> Kind<'_> {
    if arg.first() != Some(&b'-') {
        return Kind::Positional;
    }
    let exact = |b: &[u8]| {
        OPTIONS
            .iter()
            .find(|(n, _)| n.as_bytes() == b)
            .map(|&(n, _)| n)
    };
    if let Some(name) = exact(arg) {
        return Kind::Opt(name, None);
    }
    if arg.len() == 1 {
        return Kind::Positional;
    }
    if let Some(eq) = arg.iter().position(|&b| b == b'=') {
        if let Some(name) = exact(&arg[..eq]) {
            return Kind::Opt(name, Some((true, &arg[eq + 1..])));
        }
    }
    // 약어는 `--` 로 시작하는 인자에만 막혀 있다. `-h` 뒤에 글자가 붙은 `-hx` 는 `-h` 와 값 `x` 로 본다.
    if !arg.starts_with(b"--") && arg.starts_with(b"-h") {
        return Kind::Opt("-h", Some((false, &arg[2..])));
    }
    if negative_number(arg) || arg.contains(&b' ') {
        return Kind::Positional;
    }
    Kind::Unknown
}

fn is_opt(kind: &Kind) -> bool {
    matches!(kind, Kind::Opt(..) | Kind::Unknown)
}

/// 인자 문자열 목록에서 첫 `--` 를 지운다(argparse `_get_values`).
fn without_marker<'a>(strs: &[&'a [u8]]) -> Vec<&'a [u8]> {
    let mut v = strs.to_vec();
    if let Some(i) = v.iter().position(|s| *s == b"--") {
        v.remove(i);
    }
    v
}

struct Parser<'a> {
    args: &'a [Vec<u8>],
    kinds: Vec<Kind<'a>>,
    opts: Options,
    file_done: bool,
    /// 해석하지 못한 인자가 있다(끝에서 오류)
    extras: bool,
}

enum Step {
    Next(usize),
    Help,
}

impl<'a> Parser<'a> {
    fn slice(&self, from: usize, to: usize) -> Vec<&'a [u8]> {
        self.args[from..to].iter().map(Vec::as_slice).collect()
    }

    /// 위치 인자 `file`(nargs='?', 정규식 `-*A?-*`)를 소비하고 새 위치를 돌려준다.
    fn consume_positionals(&mut self, start: usize) -> usize {
        if self.file_done {
            return start;
        }
        let n = self.args.len();
        let mut i = start;
        while i < n && matches!(self.kinds[i], Kind::Marker) {
            i += 1;
        }
        if i < n && matches!(self.kinds[i], Kind::Positional) {
            i += 1;
        }
        while i < n && matches!(self.kinds[i], Kind::Marker) {
            i += 1;
        }
        self.file_done = true;
        if let Some(first) = without_marker(&self.slice(start, i)).first() {
            self.opts.file = first.to_vec();
        }
        i
    }

    fn consume_optional(&mut self, start: usize) -> Result<Step, String> {
        let n = self.args.len();
        let Kind::Opt(first_name, first_explicit) = self.kinds[start] else {
            return Ok(Step::Next(start + 1));
        };
        let mut name = first_name;
        let mut explicit = first_explicit.map(|(sep, e)| (sep, e.to_vec()));
        let mut tuples: Vec<(Act, Option<Vec<u8>>)> = Vec::new();
        let stop;
        loop {
            let Some(act) = act_of(name) else {
                return Ok(Step::Next(start + 1));
            };
            let takes = matches!(act, Act::Min | Act::Max);
            if let Some((sep, exp)) = explicit.take() {
                if !takes && name.as_bytes()[1] != b'-' && !exp.is_empty() {
                    // `-hh` 처럼 한 대시 옵션이 이어 붙은 꼴
                    if sep || exp[0] == b'-' {
                        return Err(format!(
                            "argument {name}: ignored explicit argument {}",
                            quote(&exp)
                        ));
                    }
                    tuples.push((act, None));
                    if exp[0] != b'h' {
                        // `-x` 는 알 수 없는 옵션이라 extras 로 가고, 앞의 옵션은 그대로 실행된다
                        self.extras = true;
                        stop = start + 1;
                        break;
                    }
                    name = "-h";
                    let rest = &exp[1..];
                    explicit = match rest.first() {
                        None => None,
                        Some(b'=') => Some((true, rest[1..].to_vec())),
                        Some(_) => Some((false, rest.to_vec())),
                    };
                    continue;
                } else if takes {
                    tuples.push((act, Some(exp)));
                    stop = start + 1;
                    break;
                }
                return Err(format!(
                    "argument {name}: ignored explicit argument {}",
                    quote(&exp)
                ));
            }
            if takes {
                // 옵션의 값 패턴은 `A` 하나다(argparse 는 옵션에서 `-*` 를 뺀다). `--` 는 값이 될 수 없다
                let next = start + 1;
                if next >= n || !matches!(self.kinds[next], Kind::Positional) {
                    return Err(format!("argument {name}: expected one argument"));
                }
                tuples.push((act, Some(self.args[next].clone())));
                stop = next + 1;
            } else {
                tuples.push((act, None));
                stop = start + 1;
            }
            break;
        }
        for (act, value) in tuples {
            match act {
                Act::Help => return Ok(Step::Help),
                Act::Json => self.opts.json = true,
                Act::Min | Act::Max => {
                    let flag = if act == Act::Min {
                        "--min-level"
                    } else {
                        "--max-level"
                    };
                    let level = level_of(flag, &value.unwrap_or_default())?;
                    if act == Act::Min {
                        self.opts.min_level = level;
                    } else {
                        self.opts.max_level = level;
                    }
                }
            }
        }
        Ok(Step::Next(stop))
    }
}

fn quote(bytes: &[u8]) -> String {
    format!("'{}'", String::from_utf8_lossy(bytes))
}

/// `type=int, choices=range(1, 7)`
fn level_of(flag: &str, value: &[u8]) -> Result<u8, String> {
    let parsed = std::str::from_utf8(value).ok().and_then(pystr::py_int);
    match parsed {
        None => Err(format!(
            "argument {flag}: invalid int value: {}",
            quote(value)
        )),
        Some(v @ 1..=6) => Ok(v as u8),
        Some(v) => Err(format!(
            "argument {flag}: invalid choice: {v} (choose from 1, 2, 3, 4, 5, 6)"
        )),
    }
}

fn parse_inner(args: &[Vec<u8>]) -> Result<Parsed, String> {
    let mut kinds = Vec::with_capacity(args.len());
    let mut after_marker = false;
    for arg in args {
        kinds.push(if after_marker {
            Kind::Positional
        } else if arg == b"--" {
            after_marker = true;
            Kind::Marker
        } else {
            parse_optional(arg)
        });
    }
    let n = args.len();
    let mut p = Parser {
        args,
        kinds,
        opts: Options {
            file: b"-".to_vec(),
            min_level: 1,
            max_level: 6,
            json: false,
        },
        file_done: false,
        extras: false,
    };
    let mut start = 0;
    if let Some(max_opt) = (0..n).rev().find(|&i| is_opt(&p.kinds[i])) {
        while start <= max_opt {
            let next = (start..n).find(|&i| is_opt(&p.kinds[i])).unwrap_or(max_opt);
            if start != next {
                let end = p.consume_positionals(start);
                if end > start {
                    start = end;
                    continue;
                }
                start = end;
            }
            if !is_opt(&p.kinds[start]) {
                p.extras = true;
                start = next;
            }
            if matches!(p.kinds[start], Kind::Unknown) {
                p.extras = true;
                start += 1;
                continue;
            }
            match p.consume_optional(start)? {
                Step::Help => return Ok(Parsed::Help),
                Step::Next(stop) => start = stop,
            }
        }
    }
    if p.consume_positionals(start) < n {
        p.extras = true;
    }
    if p.extras {
        return Err("unrecognized arguments".to_string());
    }
    if p.opts.min_level > p.opts.max_level {
        return Err("--min-level must not be greater than --max-level".to_string());
    }
    Ok(Parsed::Run(p.opts))
}

pub fn parse(args: &[Vec<u8>]) -> Parsed {
    parse_inner(args).unwrap_or_else(Parsed::Usage)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(args: &[&str]) -> Result<Parsed, String> {
        let args: Vec<Vec<u8>> = args.iter().map(|a| a.as_bytes().to_vec()).collect();
        parse_inner(&args)
    }

    fn ok(args: &[&str]) -> (String, u8, u8, bool) {
        match run(args) {
            Ok(Parsed::Run(o)) => (
                String::from_utf8(o.file).unwrap(),
                o.min_level,
                o.max_level,
                o.json,
            ),
            _ => panic!("{args:?} should run"),
        }
    }

    #[test]
    fn defaults_and_last_wins() {
        assert_eq!(ok(&[]), ("-".into(), 1, 6, false));
        assert_eq!(
            ok(&["a.md", "--json", "--min-level=2", "--min-level", "3"]),
            ("a.md".into(), 3, 6, true)
        );
        assert_eq!(
            ok(&["--max-level", "1", "--max-level", "4", "f"]),
            ("f".into(), 1, 4, false)
        );
        assert_eq!(ok(&["--", "--json"]), ("--json".into(), 1, 6, false));
        assert_eq!(ok(&["-5", "--min-level", "٣"]), ("-5".into(), 3, 6, false));
    }

    #[test]
    fn usage_errors() {
        for bad in [
            &["--js"][..],
            &["--min", "2"],
            &["--json=1"],
            &["a", "b"],
            &["a", "--json", "b"],
            &["--min-level"],
            &["--min-level", "--json"],
            &["--min-level", "0"],
            &["--min-level", "4", "--max-level", "2"],
            &["--bogus"],
            &["-h=x"],
            &["--min-level", "--", "3"],
            &["--min-level", "9", "-h"],
            &["-a", "b"],
        ] {
            assert!(run(bad).is_err(), "{bad:?}");
        }
    }

    #[test]
    fn help_wins_in_order() {
        for good in [
            &["-h"][..],
            &["--bogus", "-h"],
            &["-h", "--min-level", "9"],
            &["-hh"],
            &["-hx"],
            &["--help"],
        ] {
            assert!(matches!(run(good), Ok(Parsed::Help)), "{good:?}");
        }
    }
}
