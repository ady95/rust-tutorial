//! 요청 처리. 판정 순서(계약 3.5, FastAPI get_request_handler):
//! 라우트 → (본문이 있는 라우트만) 본문 해석, 실패하면 즉시 400/422 → 경로·쿼리·본문 검증 오류를 모아 422 → 락 안에서 처리

use std::net::SocketAddr;
use std::sync::Mutex;

use crate::jsonout::{push_f64, push_pystr, push_str};
use crate::lax::PyInt;
use crate::models::{self, Body, Loc, Patch, ValError};
use crate::pyjson::{self, LoadError};
use crate::router::{self, Resolved, RouteId};
use crate::store::{Item, ReserveOutcome, Store};

pub struct Request<'a> {
    pub method: &'a str,
    pub target: &'a [u8],
    /// (소문자 이름, 값 바이트), 받은 순서
    pub headers: &'a [(String, Vec<u8>)],
    pub body: &'a [u8],
    pub local: SocketAddr,
}

pub struct Response {
    pub status: u16,
    pub content_type: Option<&'static str>,
    pub location: Option<String>,
    pub allow: Option<&'static str>,
    pub body: Vec<u8>,
}

impl Response {
    fn json(status: u16, body: String) -> Response {
        Response {
            status,
            content_type: Some("application/json"),
            location: None,
            allow: None,
            body: body.into_bytes(),
        }
    }

    fn detail(status: u16, message: &str) -> Response {
        let mut out = String::from("{\"detail\":");
        push_str(&mut out, message);
        out.push('}');
        Response::json(status, out)
    }

    fn empty(status: u16) -> Response {
        Response {
            status,
            content_type: None,
            location: None,
            allow: None,
            body: Vec::new(),
        }
    }

    /// 처리되지 않은 예외(ServerErrorMiddleware)
    pub fn internal_error() -> Response {
        Response {
            status: 500,
            content_type: Some("text/plain; charset=utf-8"),
            location: None,
            allow: None,
            body: b"Internal Server Error".to_vec(),
        }
    }
}

pub struct App {
    store: Mutex<Store>,
    test_mode: bool,
}

/// Python `str.strip()` 이 지우는 문자 중 latin-1 범위
fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\t' | '\n' | '\u{b}' | '\u{c}' | '\r' | '\u{1c}'..='\u{1f}' | ' ' | '\u{85}' | '\u{a0}'
    )
}

/// email.message 의 get_content_type 으로 본 미디어 타입이 JSON 인가
pub(crate) fn is_json_content_type(value: &str) -> bool {
    let media = value.split(';').next().unwrap_or("");
    let media: String = media.trim_matches(is_py_space).to_lowercase();
    if media.matches('/').count() != 1 {
        return false;
    }
    let (main, sub) = media.split_once('/').unwrap_or(("", ""));
    main == "application" && (sub == "json" || sub.ends_with("+json"))
}

pub(crate) fn latin1(bytes: &[u8]) -> String {
    bytes.iter().map(|&b| char::from(b)).collect()
}

fn header<'a>(req: &'a Request, name: &str) -> Option<&'a [u8]> {
    req.headers
        .iter()
        .find(|(n, _)| n == name)
        .map(|(_, v)| v.as_slice())
}

fn errors_response(errors: &[ValError]) -> Response {
    let mut out = String::from("{\"detail\":[");
    for (index, error) in errors.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str("{\"type\":");
        push_str(&mut out, error.kind);
        out.push_str(",\"loc\":[");
        for (k, part) in error.loc.iter().enumerate() {
            if k > 0 {
                out.push(',');
            }
            match part {
                Loc::Index(i) => out.push_str(&i.to_string()),
                // 고립 서로게이트가 든 키는 응답을 UTF-8 로 인코딩하지 못해 500 이 된다
                Loc::Key(key) => {
                    if push_pystr(&mut out, key).is_none() {
                        return Response::internal_error();
                    }
                }
            }
        }
        out.push_str("],\"msg\":");
        push_str(&mut out, error.msg());
        out.push('}');
    }
    out.push_str("]}");
    Response::json(422, out)
}

fn push_item(out: &mut String, item: &Item) {
    out.push_str(&format!("{{\"id\":{},\"name\":", item.id));
    push_str(out, &item.name);
    out.push_str(",\"price\":");
    push_f64(out, item.price);
    out.push_str(&format!(",\"quantity\":{},\"tags\":[", item.quantity));
    for (index, tag) in item.tags.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        push_str(out, tag);
    }
    out.push_str("]}");
}

fn item_response(status: u16, item: &Item) -> Response {
    let mut out = String::new();
    push_item(&mut out, item);
    Response::json(status, out)
}

fn not_found(id: &PyInt) -> Response {
    Response::detail(404, &format!("item {id} not found"))
}

fn takes_body(route: RouteId) -> bool {
    matches!(
        route,
        RouteId::CreateItem | RouteId::PatchItem | RouteId::Reserve
    )
}

impl App {
    pub fn new(test_mode: bool) -> App {
        App {
            store: Mutex::new(Store::default()),
            test_mode,
        }
    }

    fn store(&self) -> std::sync::MutexGuard<'_, Store> {
        self.store
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// 이 요청이 본문을 읽는 라우트로 가는가(100 Continue 판단용)
    pub fn reads_body(&self, method: &str, target: &[u8]) -> bool {
        let raw_path = target.split(|&c| c == b'?').next().unwrap_or(target);
        matches!(
            router::resolve(method, &router::unquote(raw_path), self.test_mode),
            Resolved::Found(route, _) if takes_body(route)
        )
    }

    pub fn handle(&self, req: &Request) -> Response {
        let (raw_path, query) = match req.target.iter().position(|&c| c == b'?') {
            Some(q) => (&req.target[..q], &req.target[q + 1..]),
            None => (req.target, &b""[..]),
        };
        let path = router::unquote(raw_path);
        match router::resolve(req.method, &path, self.test_mode) {
            Resolved::NotFound => Response::detail(404, "Not Found"),
            Resolved::MethodNotAllowed(allow) => {
                let mut response = Response::detail(405, "Method Not Allowed");
                response.allow = Some(allow);
                response
            }
            Resolved::Redirect(stripped) => {
                let host = header(req, "host").map(latin1);
                let mut response = Response::empty(307);
                response.location = Some(router::redirect_location(
                    &stripped,
                    query,
                    host.as_deref(),
                    req.local,
                ));
                response
            }
            Resolved::Found(route, param) => self.dispatch(req, route, param, query),
        }
    }

    /// FastAPI 가 본 본문. 해석에 실패하면 바로 보낼 응답
    fn read_body(req: &Request) -> Result<Body, Response> {
        if req.body.is_empty() {
            return Ok(Body::Missing);
        }
        let content_type = header(req, "content-type").map(latin1).unwrap_or_default();
        if content_type.is_empty() || !is_json_content_type(&content_type) {
            return Ok(Body::Bytes);
        }
        match pyjson::loads(req.body) {
            Ok(value) => Ok(Body::Json(value)),
            Err(LoadError::Invalid(pos)) => Err(errors_response(&[ValError::new(
                "json_invalid",
                vec![Loc::key("body"), Loc::Index(pos)],
            )])),
            Err(LoadError::Other) => {
                Err(Response::detail(400, "There was an error parsing the body"))
            }
        }
    }

    fn dispatch(
        &self,
        req: &Request,
        route: RouteId,
        param: Option<String>,
        query: &[u8],
    ) -> Response {
        let body = if takes_body(route) {
            match App::read_body(req) {
                Ok(body) => body,
                Err(response) => return response,
            }
        } else {
            Body::Missing
        };
        let mut errors = Vec::new();
        let item_id = param.and_then(|raw| {
            models::int_param(
                &raw,
                vec![Loc::key("path"), Loc::key("item_id")],
                &mut errors,
            )
        });
        match route {
            RouteId::Health => Response::json(200, "{\"status\":\"ok\"}".into()),
            RouteId::CreateItem => {
                let Some(input) = models::item_in(&body, &mut errors) else {
                    return errors_response(&errors);
                };
                let item = self.store().create(input);
                let mut response = item_response(201, &item);
                response.location = Some(format!("/items/{}", item.id));
                response
            }
            RouteId::ListItems => self.list(query),
            RouteId::GetItem => {
                let Some(id) = item_id else {
                    return errors_response(&errors);
                };
                match self.store().get(&id) {
                    Some(item) => item_response(200, item),
                    None => not_found(&id),
                }
            }
            RouteId::PatchItem => {
                let patch = models::item_patch(&body, &mut errors);
                let (Some(id), Some(patch)) = (item_id, patch) else {
                    return errors_response(&errors);
                };
                let mut store = self.store();
                if store.get(&id).is_none() {
                    return not_found(&id);
                }
                let has_null = patch.name == Patch::Null
                    || patch.price == Patch::Null
                    || patch.quantity == Patch::Null
                    || patch.tags == Patch::Null;
                if has_null {
                    return Response::detail(400, "fields cannot be null");
                }
                match store.update(&id, patch) {
                    Some(item) => item_response(200, &item),
                    None => not_found(&id),
                }
            }
            RouteId::DeleteItem => {
                let Some(id) = item_id else {
                    return errors_response(&errors);
                };
                if self.store().delete(&id) {
                    Response::empty(204)
                } else {
                    not_found(&id)
                }
            }
            RouteId::Reserve => {
                let input = models::reserve_in(&body, &mut errors);
                let (Some(id), Some(input)) = (item_id, input) else {
                    return errors_response(&errors);
                };
                match self.store().reserve(&id, input.quantity) {
                    ReserveOutcome::NotFound => not_found(&id),
                    ReserveOutcome::Insufficient { available } => Response::detail(
                        409,
                        &format!(
                            "insufficient stock: requested {}, available {available}",
                            input.quantity
                        ),
                    ),
                    ReserveOutcome::Reserved { remaining } => Response::json(
                        200,
                        format!(
                            "{{\"item_id\":{id},\"reserved\":{},\"remaining\":{remaining}}}",
                            input.quantity
                        ),
                    ),
                }
            }
            RouteId::Stats => {
                let (count, total_quantity, total_value) = self.store().stats();
                let mut out = format!(
                    "{{\"items\":{count},\"total_quantity\":{total_quantity},\"total_value\":"
                );
                match total_value {
                    Some(value) => push_f64(&mut out, value),
                    None => out.push('0'),
                }
                out.push('}');
                Response::json(200, out)
            }
            RouteId::Reset => {
                *self.store() = Store::default();
                Response::empty(204)
            }
        }
    }

    fn list(&self, query: &[u8]) -> Response {
        let mut limit = None;
        let mut offset = None;
        let mut tag = None;
        // 같은 이름이 여러 번이면 마지막 값
        for (name, value) in router::parse_qsl(query) {
            match name.as_str() {
                "limit" => limit = Some(value),
                "offset" => offset = Some(value),
                "tag" => tag = Some(value),
                _ => {}
            }
        }
        let mut errors = Vec::new();
        let limit = match &limit {
            Some(raw) => models::bounded_param(
                raw,
                vec![Loc::key("query"), Loc::key("limit")],
                1,
                Some(100),
                &mut errors,
            ),
            None => Some(PyInt::from_i64(20)),
        };
        let offset = match &offset {
            Some(raw) => models::bounded_param(
                raw,
                vec![Loc::key("query"), Loc::key("offset")],
                0,
                None,
                &mut errors,
            ),
            None => Some(PyInt::from_i64(0)),
        };
        let (Some(limit), Some(offset)) = (limit, offset) else {
            return errors_response(&errors);
        };
        let offset = usize::try_from(offset.saturating()).unwrap_or(usize::MAX);
        let limit = usize::try_from(limit.saturating()).unwrap_or(0);
        let (page, total) = self.store().list(tag.as_deref(), offset, limit);
        let mut out = String::from("{\"items\":[");
        for (index, item) in page.iter().enumerate() {
            if index > 0 {
                out.push(',');
            }
            push_item(&mut out, item);
        }
        out.push_str(&format!("],\"total\":{total}}}"));
        Response::json(200, out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_type_detection() {
        assert!(is_json_content_type("application/json"));
        assert!(is_json_content_type("Application/JSON ; charset=utf-8"));
        assert!(is_json_content_type("application/vnd.api+json"));
        assert!(is_json_content_type("\u{1c}application/json\u{a0}"));
        assert!(!is_json_content_type("application/jsonx"));
        assert!(!is_json_content_type("application/json/x"));
        assert!(!is_json_content_type("text/plain"));
        assert!(!is_json_content_type("json"));
    }
}
