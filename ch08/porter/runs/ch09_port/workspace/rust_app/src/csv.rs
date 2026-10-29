//! Python `csv.reader(io.StringIO(text, newline=""))` 이식.
//!
//! 기본 방언(excel, strict=False)의 `_csv.c` 상태 기계를 글자 단위로 옮겼다.
//! StringIO(newline="")는 `\n`, `\r\n`, `\r` 에서 줄을 나누고, 상태 기계는 줄마다 끝에 EOL 을 하나 더 받는다.

/// `csv.field_size_limit()` 기본값. 이 글자 수(코드 포인트)까지는 허용, 한 글자 더하면 오류.
pub const FIELD_LIMIT: usize = 131_072;

#[derive(Debug, PartialEq, Eq)]
pub struct FieldTooLarge;

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    StartRecord,
    StartField,
    InField,
    InQuotedField,
    QuoteInQuotedField,
    EatCrnl,
}

struct Parse {
    state: State,
    fields: Vec<String>,
    field: String,
    field_len: usize,
}

impl Parse {
    fn add_char(&mut self, c: char) -> Result<(), FieldTooLarge> {
        if self.field_len >= FIELD_LIMIT {
            return Err(FieldTooLarge);
        }
        self.field.push(c);
        self.field_len += 1;
        Ok(())
    }

    fn save_field(&mut self) {
        self.fields.push(std::mem::take(&mut self.field));
        self.field_len = 0;
    }

    /// `c` 가 None 이면 줄 끝(EOL). `_csv.c` parse_process_char 와 같은 분기.
    fn process(&mut self, c: Option<char>) -> Result<(), FieldTooLarge> {
        let newline_or_eol = matches!(c, None | Some('\n') | Some('\r'));
        let after_line = if c.is_none() {
            State::StartRecord
        } else {
            State::EatCrnl
        };
        match self.state {
            State::StartRecord => {
                if c.is_none() {
                    // 빈 줄: [] 행
                } else if newline_or_eol {
                    self.state = State::EatCrnl;
                } else {
                    self.state = State::StartField;
                    return self.process(c);
                }
            }
            State::StartField => {
                if newline_or_eol {
                    self.save_field();
                    self.state = after_line;
                } else if c == Some('"') {
                    self.state = State::InQuotedField;
                } else if c == Some(',') {
                    self.save_field();
                } else if let Some(ch) = c {
                    self.add_char(ch)?;
                    self.state = State::InField;
                }
            }
            State::InField => {
                if newline_or_eol {
                    self.save_field();
                    self.state = after_line;
                } else if c == Some(',') {
                    self.save_field();
                    self.state = State::StartField;
                } else if let Some(ch) = c {
                    self.add_char(ch)?;
                }
            }
            State::InQuotedField => match c {
                None => {}
                Some('"') => self.state = State::QuoteInQuotedField,
                Some(ch) => self.add_char(ch)?,
            },
            State::QuoteInQuotedField => {
                if c == Some('"') {
                    self.add_char('"')?;
                    self.state = State::InQuotedField;
                } else if c == Some(',') {
                    self.save_field();
                    self.state = State::StartField;
                } else if newline_or_eol {
                    self.save_field();
                    self.state = after_line;
                } else if let Some(ch) = c {
                    // strict=False: 닫는 따옴표 뒤의 글자는 필드에 이어 붙인다
                    self.add_char(ch)?;
                    self.state = State::InField;
                }
            }
            State::EatCrnl => {
                if c.is_none() {
                    self.state = State::StartRecord;
                }
                // 줄을 \r, \n 에서만 나누므로 줄바꿈 뒤에 다른 글자가 오는 일은 없다
            }
        }
        Ok(())
    }
}

pub struct Reader<'a> {
    text: &'a str,
    pos: usize,
}

impl<'a> Reader<'a> {
    pub fn new(text: &'a str) -> Self {
        Reader { text, pos: 0 }
    }

    /// StringIO(newline="") 의 readline: 줄 끝 문자를 포함해 돌려준다.
    fn next_line(&mut self) -> Option<&'a str> {
        let rest = &self.text[self.pos..];
        if rest.is_empty() {
            return None;
        }
        let bytes = rest.as_bytes();
        let end = match bytes.iter().position(|&b| b == b'\n' || b == b'\r') {
            None => bytes.len(),
            Some(i) if bytes[i] == b'\r' && bytes.get(i + 1) == Some(&b'\n') => i + 2,
            Some(i) => i + 1,
        };
        self.pos += end;
        Some(&rest[..end])
    }
}

impl Iterator for Reader<'_> {
    type Item = Result<Vec<String>, FieldTooLarge>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut p = Parse {
            state: State::StartRecord,
            fields: Vec::new(),
            field: String::new(),
            field_len: 0,
        };
        loop {
            let Some(line) = self.next_line() else {
                // 입력 끝: 인용이 안 닫혔거나 필드가 남아 있으면 그때까지를 필드로 저장한다
                if p.field_len != 0 || p.state == State::InQuotedField {
                    p.save_field();
                    return Some(Ok(p.fields));
                }
                return None;
            };
            for c in line.chars() {
                if let Err(e) = p.process(Some(c)) {
                    self.pos = self.text.len();
                    return Some(Err(e));
                }
            }
            if let Err(e) = p.process(None) {
                self.pos = self.text.len();
                return Some(Err(e));
            }
            if p.state == State::StartRecord {
                return Some(Ok(p.fields));
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rows(text: &str) -> Vec<Vec<String>> {
        Reader::new(text).map(|r| r.unwrap()).collect()
    }

    #[test]
    fn quoting_matches_python() {
        // 기대값은 verify/probe.py 로 Python 3.12.3 에서 얻었다
        assert_eq!(rows("a\0b,c\n"), vec![vec!["a\0b", "c"]]);
        assert_eq!(rows("\"ab\"cd,x\n"), vec![vec!["abcd", "x"]]);
        assert_eq!(rows("a\"b,x\n"), vec![vec!["a\"b", "x"]]);
        assert_eq!(rows(" \"a\" ,x\n"), vec![vec![" \"a\" ", "x"]]);
        assert_eq!(rows("\"abc"), vec![vec!["abc"]]);
        assert_eq!(rows("a\rb\r\nc\n"), vec![vec!["a"], vec!["b"], vec!["c"]]);
        assert_eq!(rows("\"a\rb\"\n"), vec![vec!["a\rb"]]);
        assert_eq!(rows("\"\"\n"), vec![vec![""]]);
        assert_eq!(rows("\n\n"), vec![Vec::<String>::new(), vec![]]);
        assert_eq!(rows("\"a\"\"b\",c"), vec![vec!["a\"b", "c"]]);
        assert_eq!(rows("x,\""), vec![vec!["x", ""]]);
        assert_eq!(rows("a,\n"), vec![vec!["a", ""]]);
        assert_eq!(rows(",\n"), vec![vec!["", ""]]);
        assert!(rows("").is_empty());
    }

    #[test]
    fn field_limit_counts_code_points() {
        let ok = "가".repeat(FIELD_LIMIT);
        assert_eq!(rows(&ok)[0][0].chars().count(), FIELD_LIMIT);
        let bad = "가".repeat(FIELD_LIMIT + 1);
        assert_eq!(Reader::new(&bad).next(), Some(Err(FieldTooLarge)));
        let quoted = format!("\"{}\"\"\"", "x".repeat(FIELD_LIMIT - 1));
        assert_eq!(rows(&quoted)[0][0].len(), FIELD_LIMIT);
    }
}
