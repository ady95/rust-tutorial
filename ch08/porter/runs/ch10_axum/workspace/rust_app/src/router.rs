//! Starlette 라우팅 흉내: 디코딩된 경로를 등록 순서대로 `^...$` 정규식처럼 맞춘다.
//! Python `$` 는 문자열 끝의 '\n' 바로 앞에서도 맞으므로 끝의 개행 하나를 허용한다.

use std::net::{Ipv6Addr, SocketAddr};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RouteId {
    Health,
    CreateItem,
    ListItems,
    GetItem,
    PatchItem,
    DeleteItem,
    Reserve,
    Stats,
    Reset,
}

#[derive(Clone, Copy)]
enum Pattern {
    Fixed(&'static str),
    /// /items/{item_id}
    ItemId,
    /// /items/{item_id}/reserve
    ItemReserve,
}

struct Route {
    method: &'static str,
    pattern: Pattern,
    id: RouteId,
}

const ROUTES: [Route; 9] = [
    Route {
        method: "GET",
        pattern: Pattern::Fixed("/health"),
        id: RouteId::Health,
    },
    Route {
        method: "POST",
        pattern: Pattern::Fixed("/items"),
        id: RouteId::CreateItem,
    },
    Route {
        method: "GET",
        pattern: Pattern::Fixed("/items"),
        id: RouteId::ListItems,
    },
    Route {
        method: "GET",
        pattern: Pattern::ItemId,
        id: RouteId::GetItem,
    },
    Route {
        method: "PATCH",
        pattern: Pattern::ItemId,
        id: RouteId::PatchItem,
    },
    Route {
        method: "DELETE",
        pattern: Pattern::ItemId,
        id: RouteId::DeleteItem,
    },
    Route {
        method: "POST",
        pattern: Pattern::ItemReserve,
        id: RouteId::Reserve,
    },
    Route {
        method: "GET",
        pattern: Pattern::Fixed("/stats"),
        id: RouteId::Stats,
    },
    // STOCKROOM_TEST=1 일 때만 쓴다(목록의 마지막)
    Route {
        method: "POST",
        pattern: Pattern::Fixed("/_test/reset"),
        id: RouteId::Reset,
    },
];

pub enum Resolved {
    /// 라우트와 item_id(있으면)
    Found(RouteId, Option<String>),
    MethodNotAllowed(&'static str),
    /// 끝 '/'를 뗀 경로
    Redirect(String),
    NotFound,
}

/// `[^/]+` 다음에 문자열 끝(또는 끝 '\n' 앞)
fn is_tail(rest: &str) -> bool {
    rest.is_empty() || rest == "\n"
}

fn match_pattern(pattern: Pattern, path: &str) -> Option<Option<String>> {
    match pattern {
        Pattern::Fixed(p) => is_tail(path.strip_prefix(p)?).then_some(None),
        Pattern::ItemId => {
            let rest = path.strip_prefix("/items/")?;
            // 탐욕적 [^/]+ 가 끝까지 먹으면 '$' 는 문자열 끝에서 맞는다
            (!rest.is_empty() && !rest.contains('/')).then(|| Some(rest.to_string()))
        }
        Pattern::ItemReserve => {
            let rest = path.strip_prefix("/items/")?;
            let slash = rest.find('/')?;
            let (param, tail) = rest.split_at(slash);
            (!param.is_empty() && is_tail(tail.strip_prefix("/reserve")?))
                .then(|| Some(param.to_string()))
        }
    }
}

fn routes(with_reset: bool) -> &'static [Route] {
    if with_reset {
        &ROUTES
    } else {
        &ROUTES[..ROUTES.len() - 1]
    }
}

pub fn resolve(method: &str, path: &str, with_reset: bool) -> Resolved {
    let mut partial = None;
    for route in routes(with_reset) {
        if let Some(param) = match_pattern(route.pattern, path) {
            if route.method == method {
                return Resolved::Found(route.id, param);
            }
            partial.get_or_insert(route.method);
        }
    }
    if let Some(allow) = partial {
        return Resolved::MethodNotAllowed(allow);
    }
    if path != "/" && path.ends_with('/') {
        let stripped = path.trim_end_matches('/');
        if routes(with_reset)
            .iter()
            .any(|route| match_pattern(route.pattern, stripped).is_some())
        {
            return Resolved::Redirect(stripped.to_string());
        }
    }
    Resolved::NotFound
}

// ---- urllib.parse 호환 ----

fn hex_value(c: u8) -> Option<u8> {
    (c as char).to_digit(16).map(|d| d as u8)
}

/// `unquote_to_bytes`: 올바른 %XX 만 바이트로 바꾸고 나머지는 그대로
fn unquote_to_bytes(s: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    let mut i = 0;
    while i < s.len() {
        if s[i] == b'%' {
            if let (Some(h), Some(l)) = (
                s.get(i + 1).copied().and_then(hex_value),
                s.get(i + 2).copied().and_then(hex_value),
            ) {
                out.push(h * 16 + l);
                i += 3;
                continue;
            }
        }
        out.push(s[i]);
        i += 1;
    }
    out
}

/// `urllib.parse.unquote(s, errors="replace")` (입력은 ASCII)
pub fn unquote(s: &[u8]) -> String {
    String::from_utf8_lossy(&unquote_to_bytes(s)).into_owned()
}

/// `parse_qsl(qs.decode("latin-1"), keep_blank_values=True)`
pub fn parse_qsl(query: &[u8]) -> Vec<(String, String)> {
    let mut pairs = Vec::new();
    for part in query.split(|&c| c == b'&') {
        if part.is_empty() {
            continue;
        }
        let (name, value) = match part.iter().position(|&c| c == b'=') {
            Some(eq) => (&part[..eq], &part[eq + 1..]),
            None => (part, &b""[..]),
        };
        let plus = |s: &[u8]| -> Vec<u8> {
            s.iter()
                .map(|&c| if c == b'+' { b' ' } else { c })
                .collect()
        };
        pairs.push((unquote(&plus(name)), unquote(&plus(value))));
    }
    pairs
}

/// `quote(url, safe=":/%#?=@[]!$&'()*+,;")`
fn quote_location(url: &str) -> String {
    const SAFE: &[u8] = b":/%#?=@[]!$&'()*+,;_.-~";
    let mut out = String::with_capacity(url.len());
    for &b in url.as_bytes() {
        if b.is_ascii_alphanumeric() || SAFE.contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// Starlette `parse_host_header` 의 정규식과 포트 검사
pub(crate) fn parse_host(host: &str) -> Option<&str> {
    let (name, port) = if let Some(rest) = host.strip_prefix('[') {
        let close = rest.find(']')?;
        let inner = &rest[..close];
        let after = &rest[close + 1..];
        if !valid_bracket_host(inner) {
            return None;
        }
        (&host[..close + 2], after)
    } else {
        match host.find(':') {
            Some(colon) => (&host[..colon], &host[colon..]),
            None => (host, ""),
        }
    };
    if !name.starts_with('[') {
        const EXTRA: &[u8] = b"._~%!$&'()*+,;=-";
        if name.is_empty()
            || !name
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || EXTRA.contains(&b))
        {
            return None;
        }
    }
    if !port.is_empty() {
        let digits = port.strip_prefix(':')?;
        if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        let trimmed = digits.trim_start_matches('0');
        if trimmed.len() > 5 || trimmed.parse::<u32>().unwrap_or(0) > 65535 {
            return None;
        }
    }
    Some(host)
}

fn valid_bracket_host(inner: &str) -> bool {
    let lower = inner.to_ascii_lowercase();
    // (?P<ipv6>[a-f0-9]*:[a-f0-9.:]+) 이면 IPv6Address 로 다시 검사
    if let Some(colon) = lower.find(':') {
        let (head, tail) = lower.split_at(colon);
        if head.bytes().all(|b| b.is_ascii_hexdigit())
            && tail.len() > 1
            && tail[1..]
                .bytes()
                .all(|b| b.is_ascii_hexdigit() || b == b'.' || b == b':')
        {
            return inner.parse::<Ipv6Addr>().is_ok();
        }
    }
    // v[a-f0-9]+\.[a-z0-9._~!$&'()*+,;=:-]+ ('v' 는 소문자만)
    let Some(rest) = inner.strip_prefix('v') else {
        return false;
    };
    let Some(dot) = rest.find('.') else {
        return false;
    };
    let (ver, tail) = rest.split_at(dot);
    const EXTRA: &[u8] = b"._~!$&'()*+,;=:-";
    !ver.is_empty()
        && ver.bytes().all(|b| b.is_ascii_hexdigit())
        && tail.len() > 1
        && tail[1..]
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || EXTRA.contains(&b))
}

/// 307 Location: Starlette `URL(scope=...)` 뒤 `RedirectResponse` 의 quote
pub fn redirect_location(
    path: &str,
    query: &[u8],
    host_header: Option<&str>,
    local: SocketAddr,
) -> String {
    let netloc = match host_header.and_then(parse_host) {
        Some(host) => host.to_string(),
        None => {
            let ip = match local {
                SocketAddr::V4(a) => a.ip().to_string(),
                SocketAddr::V6(a) => format!("[{}]", a.ip()),
            };
            if local.port() == 80 {
                ip
            } else {
                format!("{ip}:{}", local.port())
            }
        }
    };
    let path = path
        .replace('?', "%3F")
        .replace('#', "%23")
        .replace('\\', "%5C");
    let mut url = format!("http://{netloc}{path}");
    if !query.is_empty() {
        url.push('?');
        url.push_str(&String::from_utf8_lossy(query));
    }
    quote_location(&url)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn found(method: &str, path: &str) -> Option<(RouteId, Option<String>)> {
        match resolve(method, path, true) {
            Resolved::Found(id, param) => Some((id, param)),
            _ => None,
        }
    }

    #[test]
    fn matching_follows_starlette() {
        assert_eq!(found("GET", "/health\n"), Some((RouteId::Health, None)));
        assert_eq!(
            found("GET", "/items/1\n"),
            Some((RouteId::GetItem, Some("1\n".into())))
        );
        assert_eq!(
            found("POST", "/items/1/reserve\n"),
            Some((RouteId::Reserve, Some("1".into())))
        );
        assert!(found("GET", "/items//1").is_none());
        assert!(matches!(
            resolve("PUT", "/items/1", true),
            Resolved::MethodNotAllowed("GET")
        ));
        assert!(matches!(
            resolve("GET", "/items/abc//", true),
            Resolved::Redirect(p) if p == "/items/abc"
        ));
        assert!(matches!(resolve("GET", "//", true), Resolved::NotFound));
        assert!(matches!(
            resolve("POST", "/_test/reset", false),
            Resolved::NotFound
        ));
    }

    #[test]
    fn url_helpers() {
        assert_eq!(unquote(b"%41%zz%e9%2"), "A%zz\u{fffd}%2");
        assert_eq!(
            parse_qsl(b"a=1&&b&c=x+y=z"),
            [
                ("a".into(), "1".into()),
                ("b".into(), "".into()),
                ("c".into(), "x y=z".into())
            ]
        );
        let local: SocketAddr = "127.0.0.1:8000".parse().unwrap();
        assert_eq!(
            redirect_location("/items é", b"limit=1", Some("testserver"), local),
            "http://testserver/items%20%C3%A9?limit=1"
        );
        assert_eq!(
            redirect_location("/items", b"", Some("bad host"), local),
            "http://127.0.0.1:8000/items"
        );
        assert_eq!(
            redirect_location("/items", b"", Some("[::1]:99"), local),
            "http://[::1]:99/items"
        );
    }
}
