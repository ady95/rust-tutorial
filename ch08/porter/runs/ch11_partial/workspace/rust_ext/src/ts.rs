//! `TS_RE.fullmatch` + `datetime.fromisoformat(...).astimezone(timezone.utc)` 이식(port/rust_reference/src/ts.rs).
//!
//! 시각은 0001-01-01T00:00:00 UTC 부터의 마이크로초(i64)로 다룬다.

const MICROS_PER_DAY: i64 = 86_400 * 1_000_000;
/// 9999-12-31 의 서수(0001-01-01 = 1)
const MAX_ORDINAL: i64 = 3_652_059;
const MAX_MICROS: i64 = MAX_ORDINAL * MICROS_PER_DAY - 1;
const DAYS_BEFORE_MONTH: [i64; 13] = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
const DAYS_IN_MONTH: [i64; 13] = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

fn is_leap(y: i64) -> bool {
    y % 4 == 0 && (y % 100 != 0 || y % 400 == 0)
}

fn days_in_month(y: i64, m: i64) -> i64 {
    if m == 2 && is_leap(y) {
        29
    } else {
        DAYS_IN_MONTH[m as usize]
    }
}

fn ymd_to_ord(y: i64, m: i64, d: i64) -> i64 {
    let y1 = y - 1;
    let before_year = y1 * 365 + y1 / 4 - y1 / 100 + y1 / 400;
    let before_month = DAYS_BEFORE_MONTH[m as usize] + i64::from(m > 2 && is_leap(y));
    before_year + before_month + d
}

/// Python `_ord2ymd`.
fn ord_to_ymd(ordinal: i64) -> (i64, i64, i64) {
    let n = ordinal - 1;
    let (n400, n) = (n / 146_097, n % 146_097);
    let (n100, n) = (n / 36_524, n % 36_524);
    let (n4, n) = (n / 1_461, n % 1_461);
    let (n1, n) = (n / 365, n % 365);
    let year = n400 * 400 + 1 + n100 * 100 + n4 * 4 + n1;
    if n1 == 4 || n100 == 4 {
        return (year - 1, 12, 31);
    }
    let leap = n1 == 3 && (n4 != 24 || n100 == 3);
    let mut month = (n + 50) >> 5;
    let mut preceding = DAYS_BEFORE_MONTH[month as usize] + i64::from(month > 2 && leap);
    if preceding > n {
        month -= 1;
        preceding -= DAYS_IN_MONTH[month as usize] + i64::from(month == 2 && leap);
    }
    (year, month, n - preceding + 1)
}

fn num(b: &[u8]) -> Option<i64> {
    if b.is_empty() || !b.iter().all(u8::is_ascii_digit) {
        return None;
    }
    Some(b.iter().fold(0, |acc, &c| acc * 10 + i64::from(c - b'0')))
}

/// 형식이나 값이 틀리면 None(`bad ts`).
pub fn parse(s: &[u8]) -> Option<i64> {
    // YYYY-MM-DDTHH:MM:SS
    if s.len() < 20
        || s[4] != b'-'
        || s[7] != b'-'
        || s[10] != b'T'
        || s[13] != b':'
        || s[16] != b':'
    {
        return None;
    }
    let year = num(&s[0..4])?;
    let month = num(&s[5..7])?;
    let day = num(&s[8..10])?;
    let hour = num(&s[11..13])?;
    let minute = num(&s[14..16])?;
    let second = num(&s[17..19])?;
    let mut rest = &s[19..];
    let mut micros = 0;
    if rest.first() == Some(&b'.') {
        let n = rest[1..].iter().take_while(|c| c.is_ascii_digit()).count();
        if !(1..=6).contains(&n) {
            return None;
        }
        micros = num(&rest[1..=n])? * 10_i64.pow(6 - n as u32);
        rest = &rest[1 + n..];
    }
    // 오프셋(분). 시·분 각각의 범위는 검사하지 않고 합이 24시간 미만이면 된다(+00:60 = +1h)
    let offset = match rest {
        b"Z" => 0,
        [sign @ (b'+' | b'-'), h1, h2, b':', m1, m2] => {
            let v = num(&[*h1, *h2])? * 60 + num(&[*m1, *m2])?;
            if *sign == b'-' {
                -v
            } else {
                v
            }
        }
        _ => return None,
    };
    if !(1..=9999).contains(&year)
        || !(1..=12).contains(&month)
        || !(1..=days_in_month(year, month)).contains(&day)
        || hour > 23
        || minute > 59
        || second > 59
        || offset.abs() >= 24 * 60
    {
        return None;
    }
    let local = (ymd_to_ord(year, month, day) - 1) * MICROS_PER_DAY
        + (hour * 3600 + minute * 60 + second) * 1_000_000
        + micros;
    let utc = local - offset * 60 * 1_000_000;
    // astimezone(utc) 결과가 1~9999년 밖이면 OverflowError
    if !(0..=MAX_MICROS).contains(&utc) {
        return None;
    }
    Some(utc)
}

pub struct Parts {
    pub year: i64,
    pub month: i64,
    pub day: i64,
    pub hour: i64,
    pub minute: i64,
    pub second: i64,
    pub micro: i64,
}

pub fn parts(t: i64) -> Parts {
    let (year, month, day) = ord_to_ymd(t / MICROS_PER_DAY + 1);
    let rem = t % MICROS_PER_DAY;
    let secs = rem / 1_000_000;
    Parts {
        year,
        month,
        day,
        hour: secs / 3600,
        minute: secs / 60 % 60,
        second: secs % 60,
        micro: rem % 1_000_000,
    }
}

/// `datetime.isoformat()` (UTC): `YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00`
pub fn isoformat(t: i64) -> String {
    let p = parts(t);
    let frac = if p.micro != 0 {
        format!(".{:06}", p.micro)
    } else {
        String::new()
    };
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}{}+00:00",
        p.year, p.month, p.day, p.hour, p.minute, p.second, frac
    )
}

/// peak_minute 의 키 `YYYY-MM-DDTHH:MMZ`
pub fn minute_key(t: i64) -> String {
    let p = parts(t);
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}Z",
        p.year, p.month, p.day, p.hour, p.minute
    )
}

/// 같은 분이면 같은 값(분 단위 순서 = 문자열 순서)
pub fn minute_index(t: i64) -> i64 {
    t / 60_000_000
}

#[cfg(test)]
mod tests {
    use super::*;

    fn iso(s: &str) -> Option<String> {
        parse(s.as_bytes()).map(isoformat)
    }

    #[test]
    fn matches_python() {
        let cases = [
            (
                "2026-01-01T00:00:00+00:60",
                Some("2025-12-31T23:00:00+00:00"),
            ),
            ("2026-01-01T00:00:00+23:60", None),
            (
                "2026-01-01T00:00:00+00:99",
                Some("2025-12-31T22:21:00+00:00"),
            ),
            ("2026-01-01T24:00:00Z", None),
            ("2100-02-29T00:00:00Z", None),
            ("9999-12-31T23:59:59-00:01", None),
            ("0001-01-01T00:00:00+00:01", None),
            (
                "2026-01-01T00:00:00.1234Z",
                Some("2026-01-01T00:00:00.123400+00:00"),
            ),
            ("2026-01-01T00:00:00.1234567Z", None),
            ("2026-01-01T00:00:00", None),
        ];
        for (input, want) in cases {
            assert_eq!(iso(input).as_deref(), want, "{input}");
        }
    }

    #[test]
    fn ordinal_round_trip() {
        for ord in (1..=MAX_ORDINAL).step_by(7) {
            let (y, m, d) = ord_to_ymd(ord);
            assert_eq!(ymd_to_ord(y, m, d), ord);
        }
        assert_eq!(
            minute_key(parse(b"0999-03-01T05:06:07Z").unwrap()),
            "0999-03-01T05:06Z"
        );
    }
}
