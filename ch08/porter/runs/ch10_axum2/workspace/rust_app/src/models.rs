//! ItemIn / ItemPatch / ReserveIn 검증(pydantic 모델과 같은 순서와 오류 type).
//!
//! 순서: 선언된 필드(name, price, quantity, tags) 차례로 → 입력 키 순서로 남은 키마다 extra_forbidden.
//! 제약은 le 를 먼저, 그다음 ge/gt 를 본다(NaN 이 less_than_equal 이 되는 이유).

use crate::lax::{self, PyInt};
use crate::pyjson::{PyStr, Value};

const MAX_VALUE: i128 = 1_000_000;

#[derive(Debug, Clone, PartialEq)]
pub enum Loc {
    Key(PyStr),
    Index(usize),
}

impl Loc {
    pub fn key(name: &str) -> Loc {
        Loc::Key(name.chars().map(u32::from).collect())
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct ValError {
    pub kind: &'static str,
    pub loc: Vec<Loc>,
}

impl ValError {
    pub fn new(kind: &'static str, loc: Vec<Loc>) -> ValError {
        ValError { kind, loc }
    }

    /// pydantic 메시지를 흉내 낸 것(비교 대상 아님)
    pub fn msg(&self) -> &'static str {
        match self.kind {
            "missing" => "Field required",
            "extra_forbidden" => "Extra inputs are not permitted",
            "model_attributes_type" => {
                "Input should be a valid dictionary or object to extract fields from"
            }
            "string_type" => "Input should be a valid string",
            "string_unicode" => {
                "Input should be a valid string, unable to parse raw data as a unicode string"
            }
            "string_too_short" => "String should have at least 1 character",
            "string_too_long" => "String should have at most the allowed number of characters",
            "float_type" => "Input should be a valid number",
            "float_parsing" => "Input should be a valid number, unable to parse string as a number",
            "int_type" => "Input should be a valid integer",
            "int_parsing" => {
                "Input should be a valid integer, unable to parse string as an integer"
            }
            "int_parsing_size" => {
                "Unable to parse input string as an integer, exceeded maximum size"
            }
            "int_from_float" => {
                "Input should be a valid integer, got a number with a fractional part"
            }
            "finite_number" => "Input should be a finite number",
            "greater_than_equal" => "Input should be greater than or equal to the minimum",
            "greater_than" => "Input should be greater than 0",
            "less_than_equal" => "Input should be less than or equal to the maximum",
            "list_type" => "Input should be a valid list",
            "too_long" => "List should have at most 10 items after validation",
            "json_invalid" => "JSON decode error",
            _ => "Invalid input",
        }
    }
}

/// 처리 함수에 넘어온 본문(FastAPI 가 본 모습)
pub enum Body {
    /// 본문 바이트가 비어 있음
    Missing,
    /// Content-Type 이 없거나 JSON 이 아니어서 bytes 그대로
    Bytes,
    Json(Value),
}

/// PATCH 필드: 보내지 않음 / null / 값
#[derive(Debug, Clone, PartialEq)]
pub enum Patch<T> {
    Absent,
    Null,
    Value(T),
}

pub struct ItemIn {
    pub name: String,
    pub price: f64,
    pub quantity: i64,
    pub tags: Vec<String>,
}

pub struct ItemPatch {
    pub name: Patch<String>,
    pub price: Patch<f64>,
    pub quantity: Patch<i64>,
    pub tags: Patch<Vec<String>>,
}

pub struct ReserveIn {
    pub quantity: i64,
}

type Errors = Vec<ValError>;

fn body_loc(name: &str) -> Vec<Loc> {
    vec![Loc::key("body"), Loc::key(name)]
}

fn check_str(value: &Value, loc: Vec<Loc>, max: usize, errors: &mut Errors) -> Option<String> {
    let kind = match lax::str_from_value(value) {
        Ok(s) => match s.chars().count() {
            0 => "string_too_short",
            n if n > max => "string_too_long",
            _ => return Some(s),
        },
        Err(kind) => kind,
    };
    errors.push(ValError::new(kind, loc));
    None
}

fn check_price(value: &Value, loc: Vec<Loc>, errors: &mut Errors) -> Option<f64> {
    let kind = match lax::float_from_value(value) {
        // NaN 은 어떤 비교도 거짓이라 le 검사에서 먼저 걸린다
        Ok(f) if f.is_nan() || f > MAX_VALUE as f64 => "less_than_equal",
        Ok(f) if f < 0.0 => "greater_than_equal",
        Ok(f) => return Some(f),
        Err(kind) => kind,
    };
    errors.push(ValError::new(kind, loc));
    None
}

/// 정수 0..=1e6(reserve 는 1..=1e6, greater_than)
fn check_quantity(
    value: &Value,
    loc: Vec<Loc>,
    strictly_positive: bool,
    errors: &mut Errors,
) -> Option<i64> {
    let kind = match lax::int_from_value(value).map(|n: PyInt| n.saturating()) {
        Ok(n) if n > MAX_VALUE => "less_than_equal",
        Ok(n) if strictly_positive && n <= 0 => "greater_than",
        Ok(n) if n < 0 => "greater_than_equal",
        Ok(n) => return Some(n as i64),
        Err(kind) => kind,
    };
    errors.push(ValError::new(kind, loc));
    None
}

fn check_tags(value: &Value, loc: Vec<Loc>, errors: &mut Errors) -> Option<Vec<String>> {
    let Value::Array(items) = value else {
        errors.push(ValError::new("list_type", loc));
        return None;
    };
    // 11번째 원소에서 길이 검사가 실패하면 모은 원소 오류를 버리고 too_long 하나만 남는다
    if items.len() > 10 {
        errors.push(ValError::new("too_long", loc));
        return None;
    }
    let before = errors.len();
    let mut tags = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        let mut item_loc = loc.clone();
        item_loc.push(Loc::Index(index));
        if let Some(tag) = check_str(item, item_loc, 20, errors) {
            tags.push(tag);
        }
    }
    (errors.len() == before).then_some(tags)
}

/// 본문이 객체면 키·값 목록, 아니면 오류를 넣고 None
fn object_fields<'a>(body: &'a Body, errors: &mut Errors) -> Option<&'a [(PyStr, Value)]> {
    let kind = match body {
        // 키 하나라도 고립 서로게이트가 있으면 다른 오류 없이 string_unicode 하나(실측)
        Body::Json(Value::Object(pairs))
            if pairs
                .iter()
                .any(|(key, _)| crate::pyjson::to_string(key).is_none()) =>
        {
            "string_unicode"
        }
        Body::Json(Value::Object(pairs)) => return Some(pairs),
        Body::Missing => "missing",
        _ => "model_attributes_type",
    };
    errors.push(ValError::new(kind, vec![Loc::key("body")]));
    None
}

fn lookup<'a>(pairs: &'a [(PyStr, Value)], name: &str) -> Option<&'a Value> {
    pairs
        .iter()
        .find(|(key, _)| key.iter().copied().eq(name.chars().map(u32::from)))
        .map(|(_, value)| value)
}

fn forbid_extra(pairs: &[(PyStr, Value)], known: &[&str], errors: &mut Errors) {
    for (key, _) in pairs {
        if !known
            .iter()
            .any(|name| key.iter().copied().eq(name.chars().map(u32::from)))
        {
            errors.push(ValError::new(
                "extra_forbidden",
                vec![Loc::key("body"), Loc::Key(key.clone())],
            ));
        }
    }
}

const ITEM_FIELDS: [&str; 4] = ["name", "price", "quantity", "tags"];

fn required<T>(
    pairs: &[(PyStr, Value)],
    name: &str,
    errors: &mut Errors,
    check: impl FnOnce(&Value, Vec<Loc>, &mut Errors) -> Option<T>,
) -> Option<T> {
    match lookup(pairs, name) {
        Some(value) => check(value, body_loc(name), errors),
        None => {
            errors.push(ValError::new("missing", body_loc(name)));
            None
        }
    }
}

fn optional<T>(
    pairs: &[(PyStr, Value)],
    name: &str,
    errors: &mut Errors,
    check: impl FnOnce(&Value, Vec<Loc>, &mut Errors) -> Option<T>,
) -> Option<Patch<T>> {
    match lookup(pairs, name) {
        None => Some(Patch::Absent),
        Some(Value::Null) => Some(Patch::Null),
        Some(value) => check(value, body_loc(name), errors).map(Patch::Value),
    }
}

pub fn item_in(body: &Body, errors: &mut Errors) -> Option<ItemIn> {
    let pairs = object_fields(body, errors)?;
    let before = errors.len();
    let name = required(pairs, "name", errors, |v, l, e| check_str(v, l, 100, e));
    let price = required(pairs, "price", errors, check_price);
    let quantity = required(pairs, "quantity", errors, |v, l, e| {
        check_quantity(v, l, false, e)
    });
    let tags = match lookup(pairs, "tags") {
        Some(value) => check_tags(value, body_loc("tags"), errors),
        None => Some(Vec::new()),
    };
    forbid_extra(pairs, &ITEM_FIELDS, errors);
    if errors.len() != before {
        return None;
    }
    Some(ItemIn {
        name: name?,
        price: price?,
        quantity: quantity?,
        tags: tags?,
    })
}

pub fn item_patch(body: &Body, errors: &mut Errors) -> Option<ItemPatch> {
    let pairs = object_fields(body, errors)?;
    let before = errors.len();
    let name = optional(pairs, "name", errors, |v, l, e| check_str(v, l, 100, e));
    let price = optional(pairs, "price", errors, check_price);
    let quantity = optional(pairs, "quantity", errors, |v, l, e| {
        check_quantity(v, l, false, e)
    });
    let tags = optional(pairs, "tags", errors, check_tags);
    forbid_extra(pairs, &ITEM_FIELDS, errors);
    if errors.len() != before {
        return None;
    }
    Some(ItemPatch {
        name: name?,
        price: price?,
        quantity: quantity?,
        tags: tags?,
    })
}

pub fn reserve_in(body: &Body, errors: &mut Errors) -> Option<ReserveIn> {
    let pairs = object_fields(body, errors)?;
    let before = errors.len();
    let quantity = required(pairs, "quantity", errors, |v, l, e| {
        check_quantity(v, l, true, e)
    });
    forbid_extra(pairs, &["quantity"], errors);
    if errors.len() != before {
        return None;
    }
    Some(ReserveIn {
        quantity: quantity?,
    })
}

/// 경로·쿼리의 정수(제약 없음)
pub fn int_param(raw: &str, loc: Vec<Loc>, errors: &mut Errors) -> Option<PyInt> {
    match lax::str_as_int(raw) {
        Ok(value) => Some(value),
        Err(kind) => {
            errors.push(ValError::new(kind, loc));
            None
        }
    }
}

/// 쿼리 정수 제약(le 먼저, 그다음 ge)
pub fn bounded_param(
    raw: &str,
    loc: Vec<Loc>,
    min: i128,
    max: Option<i128>,
    errors: &mut Errors,
) -> Option<PyInt> {
    let value = int_param(raw, loc.clone(), errors)?;
    let n = value.saturating();
    let kind = match max {
        Some(max) if n > max => "less_than_equal",
        _ if n < min => "greater_than_equal",
        _ => return Some(value),
    };
    errors.push(ValError::new(kind, loc));
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pyjson;

    fn kinds(text: &str) -> Vec<&'static str> {
        let body = Body::Json(pyjson::loads(text.as_bytes()).unwrap());
        let mut errors = Vec::new();
        item_in(&body, &mut errors);
        errors.iter().map(|e| e.kind).collect()
    }

    #[test]
    fn item_errors_in_field_then_extra_order() {
        assert_eq!(
            kinds(r#"{"extra":1,"name":"","price":-1,"quantity":1}"#),
            ["string_too_short", "greater_than_equal", "extra_forbidden"]
        );
        assert_eq!(
            kinds(r#"{"name":"a","price":NaN,"quantity":3.5}"#),
            ["less_than_equal", "int_from_float"]
        );
        assert_eq!(
            kinds(r#"{"name":"a","price":1,"quantity":1,"tags":[1,1,1,1,1,1,1,1,1,1,1]}"#),
            ["too_long"]
        );
        assert_eq!(kinds(r#"{}"#), ["missing", "missing", "missing"]);
        assert!(kinds(r#"{"name":"a","price":"1_0.5","quantity":"1_0"}"#).is_empty());
    }
}
