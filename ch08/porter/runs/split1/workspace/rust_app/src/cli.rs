//! argparse(Python 3.12) 호환 명령행 파서.
//!
//! 기준 구현은 다음 파서를 쓴다.
//!
//! ```text
//! parser = argparse.ArgumentParser(prog="wordfreq", description="Count word frequencies.")
//! parser.add_argument("file")
//! parser.add_argument("--top", type=positive_int, default=10)
//! parser.add_argument("--json", action="store_true")
//! ```
//!
//! 이 모듈은 위 설정에 대해 `argparse._parse_known_args` 의 처리 순서를 그대로 따른다
//! (`--`, `-`, `--top=1`, 접두어 약어, 반복 시 마지막 값, 음수 모양 위치 인자, `-h` 묶음 등).
//! 인자는 바이트로 다루므로 UTF-8 이 아닌 인자에서도 panic 하지 않는다.

use std::ffi::OsString;

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

/// 기본 --top 값
const DEFAULT_TOP: usize = 10;

/// positive_int 의 MAX_TOP_DIGITS. 이보다 자릿수가 많으면 "아주 큰 수"로 본다
const MAX_TOP_DIGITS: usize = 18;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Args {
    pub file: OsString,
    pub top: usize,
    pub json: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Outcome {
    /// 정상 실행
    Run(Args),
    /// -h/--help: 도움말을 stdout 에 쓰고 0 으로 끝낸다
    Help,
    /// 인자 오류: stderr 에 사용법과 메시지를 쓰고 2 로 끝낸다 (메시지는 계약상 비교 안 함)
    Usage(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Action {
    Help,
    Top,
    Json,
}

impl Action {
    /// argparse 의 nargs: help·json 은 0, top 은 1
    fn nargs(self) -> usize {
        match self {
            Action::Help | Action::Json => 0,
            Action::Top => 1,
        }
    }

    fn display(self) -> &'static str {
        match self {
            Action::Help => "-h/--help",
            Action::Top => "--top",
            Action::Json => "--json",
        }
    }
}

/// `parser._option_string_actions` 의 삽입 순서
const OPTION_STRINGS: [(&[u8], Action); 4] = [
    (b"-h", Action::Help),
    (b"--help", Action::Help),
    (b"--top", Action::Top),
    (b"--json", Action::Json),
];

fn lookup(option: &[u8]) -> Option<Action> {
    OPTION_STRINGS
        .iter()
        .find(|(name, _)| *name == option)
        .map(|(_, action)| *action)
}

/// argparse 의 option tuple: (action, option_string, sep, explicit_arg)
#[derive(Debug, Clone, PartialEq, Eq)]
struct OptTuple {
    action: Option<Action>,
    option_string: Vec<u8>,
    /// None = 구분자 없음, Some(false) = '' (단일 대시 붙여 쓰기), Some(true) = '='
    sep_eq: Option<bool>,
    explicit: Option<Vec<u8>>,
}

/// 패턴 문자: 'A' 위치 인자, 'O' 옵션, '-' 첫 번째 `--`
#[derive(Debug, Clone, PartialEq, Eq)]
enum Kind {
    Pos,
    Dash,
    Opt(OptTuple),
}

impl Kind {
    fn code(&self) -> u8 {
        match self {
            Kind::Pos => b'A',
            Kind::Dash => b'-',
            Kind::Opt(_) => b'O',
        }
    }
}

struct UsageError(String);

fn lossy(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

/// Python repr() 비슷한 따옴표 표기 (메시지용, 비교 대상 아님)
fn quoted(bytes: &[u8]) -> String {
    format!("'{}'", lossy(bytes))
}

/// 인자의 원래 바이트. Unix 에서는 OS 가 준 바이트 그대로다
pub fn os_bytes(arg: &std::ffi::OsStr) -> Vec<u8> {
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

/// 오류 메시지에 넣을 이름: UTF-8 이 아닌 부분은 최대 부분마다 U+FFFD (계약 4절)
pub fn display_name(arg: &std::ffi::OsStr) -> String {
    lossy(&os_bytes(arg))
}

/// Python 3.12 re 의 `\d`(str 패턴) 집합 = Unicode 15.0 의 Nd.
/// verify/gen_props.py 로 Python 에서 뽑았다 (rust_app/tests/data/py_props.txt 와 단위 테스트로 대조).
const PY_DIGIT_RANGES: [(u32, u32); 64] = [
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

pub fn is_py_digit(c: char) -> bool {
    let cp = u32::from(c);
    PY_DIGIT_RANGES.iter().any(|&(lo, hi)| lo <= cp && cp <= hi)
}

/// `re.match(r'^-\d+$|^-\d*\.\d+$', s)`. `$` 는 끝 또는 마지막 '\n' 바로 앞에서 맞는다
fn looks_like_negative_number(arg: &[u8]) -> bool {
    let Ok(text) = std::str::from_utf8(arg) else {
        // UTF-8 이 아닌 바이트는 Python 에서 서로게이트 글자가 되어 어느 쪽에도 맞지 않는다
        return false;
    };
    let body = text.strip_suffix('\n').unwrap_or(text);
    let Some(rest) = body.strip_prefix('-') else {
        return false;
    };
    let all_digits = |s: &str| s.chars().all(is_py_digit);
    if !rest.is_empty() && all_digits(rest) {
        return true;
    }
    match rest.split_once('.') {
        Some((int_part, frac)) => !frac.is_empty() && all_digits(int_part) && all_digits(frac),
        None => false,
    }
}

fn split_eq(arg: &[u8]) -> (&[u8], Option<&[u8]>) {
    match arg.iter().position(|&b| b == b'=') {
        Some(pos) => (&arg[..pos], Some(&arg[pos + 1..])),
        None => (arg, None),
    }
}

/// argparse `_parse_optional`. Ok(None) 은 위치 인자
fn parse_optional(arg: &[u8]) -> Result<Option<OptTuple>, UsageError> {
    if arg.first() != Some(&b'-') {
        return Ok(None);
    }
    if let Some(action) = lookup(arg) {
        return Ok(Some(OptTuple {
            action: Some(action),
            option_string: arg.to_vec(),
            sep_eq: None,
            explicit: None,
        }));
    }
    if arg.len() == 1 {
        return Ok(None);
    }
    let (name, value) = split_eq(arg);
    if let Some(value) = value {
        if let Some(action) = lookup(name) {
            return Ok(Some(OptTuple {
                action: Some(action),
                option_string: name.to_vec(),
                sep_eq: Some(true),
                explicit: Some(value.to_vec()),
            }));
        }
    }

    let tuples = option_tuples(arg);
    if tuples.len() > 1 {
        let names: Vec<String> = tuples.iter().map(|t| lossy(&t.option_string)).collect();
        return Err(UsageError(format!(
            "ambiguous option: {} could match {}",
            lossy(arg),
            names.join(", ")
        )));
    }
    if let Some(tuple) = tuples.into_iter().next() {
        return Ok(Some(tuple));
    }
    if looks_like_negative_number(arg) {
        return Ok(None);
    }
    if arg.contains(&b' ') {
        return Ok(None);
    }
    Ok(Some(OptTuple {
        action: None,
        option_string: arg.to_vec(),
        sep_eq: None,
        explicit: None,
    }))
}

/// argparse `_get_option_tuples` (allow_abbrev=True). arg 는 '-' 로 시작하고 길이 2 이상
fn option_tuples(arg: &[u8]) -> Vec<OptTuple> {
    let mut result = Vec::new();
    if arg.get(1) == Some(&b'-') {
        let (prefix, value) = split_eq(arg);
        for (name, action) in OPTION_STRINGS {
            if name.starts_with(prefix) {
                result.push(OptTuple {
                    action: Some(action),
                    option_string: name.to_vec(),
                    sep_eq: value.map(|_| true),
                    explicit: value.map(<[u8]>::to_vec),
                });
            }
        }
    } else {
        // 단일 대시: 앞 두 글자가 옵션 이름과 같으면 나머지를 붙여 쓴 값으로 본다.
        // 옵션 이름이 모두 ASCII 이므로 바이트 비교로 충분하다
        let short = arg.get(..2);
        for (name, action) in OPTION_STRINGS {
            if Some(name) == short {
                result.push(OptTuple {
                    action: Some(action),
                    option_string: name.to_vec(),
                    sep_eq: Some(false),
                    explicit: Some(arg.get(2..).unwrap_or_default().to_vec()),
                });
            } else if name.starts_with(arg) {
                result.push(OptTuple {
                    action: Some(action),
                    option_string: name.to_vec(),
                    sep_eq: None,
                    explicit: None,
                });
            }
        }
    }
    result
}

/// 첫 글자(UTF-8 한 글자, 깨진 바이트면 1바이트)의 길이
fn first_char_len(bytes: &[u8]) -> usize {
    match bytes.first() {
        None => 0,
        Some(&b) if b < 0x80 => 1,
        Some(_) => {
            let take = bytes.len().min(4);
            for n in (1..=take).rev() {
                if std::str::from_utf8(&bytes[..n]).is_ok() {
                    return n;
                }
            }
            1
        }
    }
}

/// 계약 1절 / 기준 구현 positive_int
pub fn positive_int(value: &[u8]) -> Result<usize, String> {
    if value.is_empty() || !value.iter().all(u8::is_ascii_digit) {
        return Err(format!("not an integer: {}", lossy(value)));
    }
    let start = value.iter().position(|&b| b != b'0').unwrap_or(value.len());
    let digits = &value[start..];
    if digits.is_empty() {
        return Err(format!("must be at least 1: {}", lossy(value)));
    }
    if digits.len() > MAX_TOP_DIGITS {
        return Ok(usize::MAX);
    }
    let mut n: u64 = 0;
    for &d in digits {
        // 18자리 이하이므로 u64 에서 넘치지 않는다
        n = n * 10 + u64::from(d - b'0');
    }
    Ok(usize::try_from(n).unwrap_or(usize::MAX))
}

struct State<'a> {
    args: &'a [OsString],
    raw: Vec<Vec<u8>>,
    kinds: Vec<Kind>,
    pattern: Vec<u8>,
    file: Option<OsString>,
    top: usize,
    json: bool,
    extras: Vec<Vec<u8>>,
}

enum Stop {
    Help,
    Error(UsageError),
}

impl From<UsageError> for Stop {
    fn from(err: UsageError) -> Self {
        Stop::Error(err)
    }
}

impl State<'_> {
    /// `consume_positionals`: 위치 인자 file 의 패턴 '(-*A-*)'
    fn consume_positionals(&mut self, start: usize) -> usize {
        if self.file.is_some() {
            return start;
        }
        let rest = self.pattern.get(start..).unwrap_or_default();
        let mut i = 0;
        while rest.get(i) == Some(&b'-') {
            i += 1;
        }
        if rest.get(i) != Some(&b'A') {
            return start;
        }
        i += 1;
        while rest.get(i) == Some(&b'-') {
            i += 1;
        }
        // 인자 목록에서 첫 '--' 를 지운다 (_get_values 의 arg_strings.remove('--'))
        let mut taken: Vec<usize> = (start..start + i).collect();
        if let Some(pos) = taken.iter().position(|&k| self.raw[k] == b"--") {
            taken.remove(pos);
        }
        if let Some(&k) = taken.first() {
            self.file = Some(self.args[k].clone());
        }
        start + i
    }

    /// `consume_optional`
    fn consume_optional(&mut self, start: usize) -> Result<usize, Stop> {
        let Kind::Opt(tuple) = self.kinds[start].clone() else {
            return Ok(start + 1);
        };
        let OptTuple {
            mut action,
            mut option_string,
            mut sep_eq,
            mut explicit,
        } = tuple;
        let mut action_tuples: Vec<(Action, Option<Vec<u8>>)> = Vec::new();
        let stop;
        loop {
            let Some(act) = action else {
                self.extras.push(self.raw[start].clone());
                return Ok(start + 1);
            };
            if let Some(exp) = explicit.take() {
                let arg_count = act.nargs();
                if arg_count == 0 && option_string.get(1) != Some(&b'-') && !exp.is_empty() {
                    if sep_eq == Some(true) || exp.first() == Some(&b'-') {
                        return Err(Stop::Error(UsageError(format!(
                            "argument {}: ignored explicit argument {}",
                            act.display(),
                            quoted(&exp)
                        ))));
                    }
                    action_tuples.push((act, None));
                    let n = first_char_len(&exp);
                    let mut next_option = vec![b'-'];
                    next_option.extend_from_slice(&exp[..n]);
                    if let Some(next) = lookup(&next_option) {
                        action = Some(next);
                        option_string = next_option;
                        let rest = &exp[n..];
                        if rest.is_empty() {
                            sep_eq = None;
                            explicit = None;
                        } else if rest[0] == b'=' {
                            sep_eq = Some(true);
                            explicit = Some(rest[1..].to_vec());
                        } else {
                            sep_eq = Some(false);
                            explicit = Some(rest.to_vec());
                        }
                    } else {
                        let mut extra = vec![b'-'];
                        extra.extend_from_slice(&exp);
                        self.extras.push(extra);
                        stop = start + 1;
                        break;
                    }
                } else if arg_count == 1 {
                    stop = start + 1;
                    action_tuples.push((act, Some(exp)));
                    break;
                } else {
                    return Err(Stop::Error(UsageError(format!(
                        "argument {}: ignored explicit argument {}",
                        act.display(),
                        quoted(&exp)
                    ))));
                }
            } else {
                let next = start + 1;
                let arg_count = act.nargs();
                if arg_count == 1 {
                    // 옵션의 패턴 '(A)': 바로 다음이 위치 인자여야 한다
                    if self.pattern.get(next) != Some(&b'A') {
                        return Err(Stop::Error(UsageError(format!(
                            "argument {}: expected one argument",
                            act.display()
                        ))));
                    }
                    action_tuples.push((act, Some(self.raw[next].clone())));
                } else {
                    action_tuples.push((act, None));
                }
                stop = next + arg_count;
                break;
            }
        }
        for (act, value) in action_tuples {
            match act {
                Action::Help => return Err(Stop::Help),
                Action::Json => self.json = true,
                Action::Top => {
                    let value = value.unwrap_or_default();
                    match positive_int(&value) {
                        Ok(n) => self.top = n,
                        Err(msg) => {
                            return Err(Stop::Error(UsageError(format!("argument --top: {msg}"))))
                        }
                    }
                }
            }
        }
        Ok(stop)
    }
}

/// argv[1:] 를 해석한다
pub fn parse(args: &[OsString]) -> Outcome {
    match parse_inner(args) {
        Ok(parsed) => Outcome::Run(parsed),
        Err(Stop::Help) => Outcome::Help,
        Err(Stop::Error(UsageError(msg))) => Outcome::Usage(msg),
    }
}

fn parse_inner(args: &[OsString]) -> Result<Args, Stop> {
    let raw: Vec<Vec<u8>> = args.iter().map(|a| os_bytes(a)).collect();

    // 1단계: 각 인자를 'A' / 'O' / '-' 로 분류 (모호한 약어 오류는 여기서 바로 난다)
    let mut kinds = Vec::with_capacity(raw.len());
    let mut after_dashdash = false;
    for arg in &raw {
        if after_dashdash {
            kinds.push(Kind::Pos);
        } else if arg.as_slice() == b"--" {
            after_dashdash = true;
            kinds.push(Kind::Dash);
        } else {
            match parse_optional(arg)? {
                Some(tuple) => kinds.push(Kind::Opt(tuple)),
                None => kinds.push(Kind::Pos),
            }
        }
    }
    let pattern: Vec<u8> = kinds.iter().map(Kind::code).collect();
    let option_indices: Vec<usize> = kinds
        .iter()
        .enumerate()
        .filter(|(_, k)| matches!(k, Kind::Opt(_)))
        .map(|(i, _)| i)
        .collect();

    let mut state = State {
        args,
        raw,
        kinds,
        pattern,
        file: None,
        top: DEFAULT_TOP,
        json: false,
        extras: Vec::new(),
    };

    // 2단계: 위치 인자와 옵션을 번갈아 소비
    let mut start = 0usize;
    if let Some(&max_option) = option_indices.last() {
        while start <= max_option {
            let Some(&next_option) = option_indices.iter().find(|&&i| i >= start) else {
                break;
            };
            if start != next_option {
                let end = state.consume_positionals(start);
                if end > start {
                    start = end;
                    continue;
                }
                start = end;
            }
            if !option_indices.contains(&start) {
                for k in start..next_option {
                    let extra = state.raw[k].clone();
                    state.extras.push(extra);
                }
                start = next_option;
            }
            start = state.consume_optional(start)?;
        }
    }
    let stop = state.consume_positionals(start);
    for k in stop..state.raw.len() {
        let extra = state.raw[k].clone();
        state.extras.push(extra);
    }

    let Some(file) = state.file else {
        return Err(Stop::Error(UsageError(
            "the following arguments are required: file".to_string(),
        )));
    };
    if !state.extras.is_empty() {
        let names: Vec<String> = state.extras.iter().map(|e| lossy(e)).collect();
        return Err(Stop::Error(UsageError(format!(
            "unrecognized arguments: {}",
            names.join(" ")
        ))));
    }
    Ok(Args {
        file,
        top: state.top,
        json: state.json,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn os(args: &[&[u8]]) -> Vec<OsString> {
        args.iter()
            .map(|a| {
                #[cfg(unix)]
                {
                    use std::os::unix::ffi::OsStringExt;
                    OsString::from_vec(a.to_vec())
                }
                #[cfg(not(unix))]
                {
                    OsString::from(String::from_utf8_lossy(a).into_owned())
                }
            })
            .collect()
    }

    fn run(args: &[&[u8]]) -> Outcome {
        parse(&os(args))
    }

    fn ok(file: &str, top: usize, json: bool) -> Outcome {
        Outcome::Run(Args {
            file: OsString::from(file),
            top,
            json,
        })
    }

    fn is_usage(outcome: &Outcome) -> bool {
        matches!(outcome, Outcome::Usage(_))
    }

    #[test]
    fn positive_int_rules() {
        // 기대값: tests/test_wordfreq.py 와 verify/probe_cli.py 의 Python 실행 결과
        for bad in [
            "２", "1_0", "+3", " 3", "3 ", "-1", "", "0", "000", "abc", "\u{663}",
        ] {
            assert!(positive_int(bad.as_bytes()).is_err(), "{bad:?}");
        }
        assert_eq!(positive_int(b"002"), Ok(2));
        assert_eq!(
            positive_int(b"999999999999999999"),
            Ok(999_999_999_999_999_999)
        );
        assert_eq!(positive_int(b"1000000000000000000"), Ok(usize::MAX));
        assert_eq!(positive_int("9".repeat(5000).as_bytes()), Ok(usize::MAX));
        assert!(positive_int(b"\xff").is_err());
    }

    #[test]
    fn r4_argparse_syntax() {
        // 기대값은 verify/probe_cli.py --show 의 Python 3.12.3 실행 결과에서 옮겼다
        assert_eq!(run(&[b"f", b"--to", b"2"]), ok("f", 2, false));
        assert_eq!(run(&[b"f", b"--t", b"2"]), ok("f", 2, false));
        assert_eq!(run(&[b"f", b"--js"]), ok("f", 10, true));
        assert_eq!(run(&[b"f", b"--j"]), ok("f", 10, true));
        assert_eq!(run(&[b"f", b"--t=2"]), ok("f", 2, false));
        assert_eq!(run(&[b"f", b"--top=1"]), ok("f", 1, false));
        assert_eq!(
            run(&[b"f", b"--top", b"1", b"--top", b"2"]),
            ok("f", 2, false)
        );
        assert_eq!(run(&[b"--top", b"2", b"f"]), ok("f", 2, false));
        assert_eq!(run(&[b"--json", b"f"]), ok("f", 10, true));
        assert_eq!(run(&[b"f", b"--json", b"--json"]), ok("f", 10, true));
        assert_eq!(run(&[b"-"]), ok("-", 10, false));
        assert_eq!(run(&[b"--", b"f"]), ok("f", 10, false));
        assert_eq!(run(&[b"--", b"-x"]), ok("-x", 10, false));
        assert_eq!(run(&[b"--", b"--"]), ok("--", 10, false));
        assert_eq!(run(&[b"--json", b"--", b"f"]), ok("f", 10, true));
        assert_eq!(run(&[b"f", b"--"]), ok("f", 10, false));
        assert_eq!(run(&[b"-5"]), ok("-5", 10, false));
        assert_eq!(run(&[b"-1.5"]), ok("-1.5", 10, false));
        assert_eq!(run(&[b"-.5"]), ok("-.5", 10, false));
        assert_eq!(run(&["-\u{663}".as_bytes()]), ok("-\u{663}", 10, false));
        assert_eq!(run(&["-\u{ff15}".as_bytes()]), ok("-\u{ff15}", 10, false));
        assert_eq!(run(&[b"-5\n"]), ok("-5\n", 10, false));
        assert_eq!(run(&[b"- x"]), ok("- x", 10, false));
        assert_eq!(run(&[b"--foo bar"]), ok("--foo bar", 10, false));
        assert_eq!(run(&[b""]), ok("", 10, false));

        for args in [
            &[b"f".as_slice(), b"--top=".as_slice()][..],
            &[b"f", b"--top", b"0", b"--top", b"2"],
            &[b"f", b"--top", b"2", b"--top", b"0"],
            &[b"f", b"g"],
            &[b"f", b"--json=1"],
            &[b"f", b"--json="],
            &[b"f", b"--top"],
            &[b"f", b"--top", b"--json"],
            &[b"f", b"--top", b"--", b"2"],
            &[b"f", b"--top", b"-1"],
            &[b"--"],
            &[b"--", b"f", b"--json"],
            &[b"f", b"--json", b"--"],
            &[b"f", b"--", b"--"],
            &[b"-5\n\n"],
            &[b"-5x"],
            &[b"f", b"-5"],
            &[b"-x.txt"],
            &[b"f", b"---"],
            &[b"f", b"--=x"],
            &[b"-h-x"],
            &[b"-h=x"],
            &[b"--help=x"],
            &[b"f", b"--top", b"0", b"-h"],
            &[],
            &[b"f", b"--bogus"],
        ] {
            assert!(is_usage(&run(args)), "{args:?}");
        }
    }

    #[test]
    fn r4_help() {
        for args in [
            &[b"-h".as_slice()][..],
            &[b"--help"],
            &[b"--he"],
            &[b"--h"],
            &[b"-hh"],
            &[b"-hfoo"],
            &[b"f", b"-h"],
            &[b"--bogus", b"-h"],
            &[b"-h", b"f", b"--top", b"0"],
        ] {
            assert_eq!(run(args), Outcome::Help, "{args:?}");
        }
    }

    #[test]
    fn r12_non_utf8_arguments_are_usage_errors() {
        // 기준 구현은 UnicodeEncodeError 로 1 을 내지만 계약 4절에 따라 2 (인자 오류)
        for args in [
            &[b"f".as_slice(), b"--top".as_slice(), b"\xff".as_slice()][..],
            &[b"f", b"--\xff"],
            &[b"f", b"\xff"],
            &[b"f", b"--top=\xff"],
        ] {
            assert!(is_usage(&run(args)), "{args:?}");
        }
    }

    #[test]
    fn non_utf8_file_argument_is_kept() {
        let parsed = run(&[b"bad\xffname.txt"]);
        let Outcome::Run(args) = parsed else {
            panic!("expected run");
        };
        assert_eq!(os_bytes(&args.file), b"bad\xffname.txt");
        assert_eq!(display_name(&args.file), "bad\u{fffd}name.txt");
    }

    #[test]
    fn digit_table_matches_python() {
        let data = include_str!("../tests/data/py_props.txt");
        let mut expected = vec![false; 0x110000];
        for line in data.lines().filter(|l| l.starts_with("DIGIT ")) {
            let mut parts = line.split(' ').skip(1);
            let lo = u32::from_str_radix(parts.next().unwrap_or("0"), 16).unwrap_or(0);
            let hi = u32::from_str_radix(parts.next().unwrap_or("0"), 16).unwrap_or(0);
            for cp in lo..=hi {
                expected[cp as usize] = true;
            }
        }
        let mut diffs = Vec::new();
        for cp in 0..0x110000u32 {
            if let Some(c) = char::from_u32(cp) {
                if is_py_digit(c) != expected[cp as usize] {
                    diffs.push(cp);
                }
            }
        }
        assert!(diffs.is_empty(), "digit differences: {diffs:X?}");
    }
}
