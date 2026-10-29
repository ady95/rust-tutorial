//! 코드 블록 밖의 ATX 제목 찾기 (python_src 의 FENCE, HEADING, CLOSING 정규식과 같은 의미).

use crate::pystr;

/// FENCE: 앞 공백 0~3칸 뒤의 같은 글자 3개 이상. (글자, 개수, 나머지)
fn fence(line: &str) -> Option<(u8, usize, &str)> {
    let bytes = line.as_bytes();
    let indent = bytes.iter().take_while(|&&b| b == b' ').count();
    if indent > 3 {
        return None;
    }
    let mark = *bytes.get(indent)?;
    if mark != b'`' && mark != b'~' {
        return None;
    }
    let run = bytes[indent..].iter().take_while(|&&b| b == mark).count();
    (run >= 3).then(|| (mark, run, &line[indent + run..]))
}

/// HEADING: 앞 공백 0~3칸, `#` 1~6개, 공백·탭 하나 이상 또는 줄 끝. (수준, `#` 뒤 공백을 뺀 나머지)
fn heading(line: &str) -> Option<(u8, &str)> {
    let bytes = line.as_bytes();
    let indent = bytes.iter().take_while(|&&b| b == b' ').count();
    if indent > 3 {
        return None;
    }
    let hashes = bytes[indent..].iter().take_while(|&&b| b == b'#').count();
    if !(1..=6).contains(&hashes) {
        return None;
    }
    let rest = &line[indent + hashes..];
    if rest.is_empty() {
        return Some((hashes as u8, rest));
    }
    if !rest.starts_with([' ', '\t']) {
        return None;
    }
    Some((hashes as u8, rest.trim_start_matches([' ', '\t'])))
}

/// CLOSING: `(?:^|[ \t]+)#+[ \t]*$` 에 맞는 끝부분을 지운다.
fn strip_closing(raw: &str) -> &str {
    let trimmed = raw.trim_end_matches([' ', '\t']);
    let before = trimmed.trim_end_matches('#');
    if before.len() == trimmed.len() {
        return raw;
    }
    if before.is_empty() {
        return "";
    }
    let without_space = before.trim_end_matches([' ', '\t']);
    if without_space.len() < before.len() {
        without_space
    } else {
        raw
    }
}

/// 코드 블록 밖의 ATX 제목을 (수준, 제목) 목록으로.
pub fn headings(text: &str) -> Vec<(u8, &str)> {
    let mut found = Vec::new();
    let mut open: Option<(u8, usize)> = None;
    for line in pystr::splitlines(text) {
        let m = fence(line);
        if let Some((mark, len)) = open {
            if let Some((m_mark, m_len, info)) = m {
                if m_mark == mark && m_len >= len && pystr::strip_space_tab(info).is_empty() {
                    open = None;
                }
            }
            continue;
        }
        if let Some((mark, len, info)) = m {
            if !(mark == b'`' && info.contains('`')) {
                open = Some((mark, len));
                continue;
            }
        }
        if let Some((level, raw)) = heading(line) {
            let title = pystr::strip(strip_closing(raw));
            if !title.is_empty() {
                found.push((level, title));
            }
        }
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    fn titles(text: &str) -> Vec<(u8, &str)> {
        headings(text)
    }

    #[test]
    fn atx_rules() {
        let text = "# a\n#b\n####### seven\n    # four\n\t# tab\n   # three\n#\n# \n# ##\n## Closing ##\n# hash#\n# a # #\n###### Six ######   \n# a #\x1f\n";
        assert_eq!(
            titles(text),
            [
                (1, "a"),
                (1, "three"),
                (2, "Closing"),
                (1, "hash#"),
                (1, "a #"),
                (6, "Six"),
                (1, "a #")
            ]
        );
    }

    #[test]
    fn closing_hashes() {
        assert_eq!(strip_closing("a #"), "a");
        assert_eq!(strip_closing("a\t##\t"), "a");
        assert_eq!(strip_closing("a #b"), "a #b");
        assert_eq!(strip_closing("#  #"), "#");
        assert_eq!(strip_closing("##"), "");
    }

    #[test]
    fn fences() {
        let text = "```\n# in\n~~~\n```` \n# in\n```\n````\n# out\n~~~ a`b\n# in\n~~~\n``` a`b\n# yes\n    ```\n# yes2\n";
        // "```` " 는 닫는 줄이라 그 뒤의 "# in" 은 제목이다
        assert_eq!(
            titles(text),
            [(1, "in"), (1, "out"), (1, "yes"), (1, "yes2")]
        );
        assert_eq!(titles("```\n# never closed"), []);
        assert_eq!(
            titles("~~~~\n~~~\n# in\n~~~~ x\n# in\n~~~~\n# out"),
            [(1, "out")]
        );
    }
}
