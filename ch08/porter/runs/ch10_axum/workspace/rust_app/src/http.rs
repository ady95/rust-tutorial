//! HTTP 서버 계층(axum/hyper + tokio). 모든 요청을 fallback 처리기 하나로 받아 기존 라우터(`App`)에 넘긴다.
//! 경로 규칙(307, Allow, HEAD 미처리, 원래 경로 문자열 기준)은 axum 라우터가 아니라 `router.rs` 가 판정한다.

use std::net::SocketAddr;
use std::sync::Arc;

use axum::body::{Body, Bytes};
use axum::extract::connect_info::Connected;
use axum::extract::{DefaultBodyLimit, State};
use axum::http::header::{HeaderName, ALLOW, CONTENT_TYPE, LOCATION};
use axum::http::{HeaderValue, Request as HttpRequest, StatusCode};
use axum::response::Response as HttpResponse;
use axum::serve::IncomingStream;
use axum::Router;
use tokio::net::TcpListener;

use crate::handlers::{App, Request, Response};

/// 연결이 받아들여진 로컬 주소(리디렉션의 Location 에 쓴다)
#[derive(Clone, Copy)]
struct Local(SocketAddr);

impl Connected<IncomingStream<'_, TcpListener>> for Local {
    fn connect_info(stream: IncomingStream<'_, TcpListener>) -> Self {
        Local(
            stream
                .io()
                .local_addr()
                .unwrap_or_else(|_| SocketAddr::from(([0, 0, 0, 0], 0))),
        )
    }
}

pub async fn serve(listener: TcpListener, app: Arc<App>) -> std::io::Result<()> {
    let router = Router::new()
        .fallback(dispatch)
        .layer(DefaultBodyLimit::disable())
        .with_state(app);
    axum::serve(
        listener,
        router.into_make_service_with_connect_info::<Local>(),
    )
    .await
}

async fn dispatch(
    State(app): State<Arc<App>>,
    axum::extract::ConnectInfo(Local(local)): axum::extract::ConnectInfo<Local>,
    request: HttpRequest<Body>,
) -> HttpResponse {
    let (parts, body) = request.into_parts();
    let Ok(body): Result<Bytes, _> = axum::body::to_bytes(body, usize::MAX).await else {
        return plain(StatusCode::BAD_REQUEST);
    };
    let target = parts
        .uri
        .path_and_query()
        .map_or("/", |pq| pq.as_str())
        .as_bytes();
    let headers: Vec<(String, Vec<u8>)> = parts
        .headers
        .iter()
        .map(|(name, value)| (name.as_str().to_string(), value.as_bytes().to_vec()))
        .collect();
    let method = parts.method.as_str();
    let req = Request {
        method,
        target,
        headers: &headers,
        body: &body,
        local,
    };
    // 처리 중 패닉은 Python 의 처리되지 않은 예외처럼 500 으로 바꾼다
    let response = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| app.handle(&req)))
        .unwrap_or_else(|_| Response::internal_error());
    convert(response)
}

fn plain(status: StatusCode) -> HttpResponse {
    let mut response = HttpResponse::new(Body::empty());
    *response.status_mut() = status;
    response
}

fn convert(response: Response) -> HttpResponse {
    let status = StatusCode::from_u16(response.status).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
    let mut out = HttpResponse::new(Body::from(response.body));
    *out.status_mut() = status;
    let headers = out.headers_mut();
    let mut put = |name: HeaderName, value: &str| {
        if let Ok(value) = HeaderValue::from_str(value) {
            headers.insert(name, value);
        }
    };
    if let Some(content_type) = response.content_type {
        put(CONTENT_TYPE, content_type);
    }
    if let Some(location) = &response.location {
        put(LOCATION, location);
    }
    if let Some(allow) = response.allow {
        put(ALLOW, allow);
    }
    out
}
