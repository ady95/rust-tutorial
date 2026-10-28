//! Python과 Rust가 다르게 동작하는 지점을 한 줄씩 출력한다 (03-2).
//! python_side.py 와 같은 항목 이름을 같은 순서로 출력한다.

use std::collections::{HashMap, HashSet};

fn show(name: &str, value: impl std::fmt::Display) {
    println!("{name}\t{value}");
}

fn try_int(text: &str) -> String {
    match text.parse::<i64>() {
        Ok(n) => n.to_string(),
        Err(_) => "error".to_string(),
    }
}

fn main() {
    // 1. 정수 나눗셈과 나머지 (음수)
    show("int.div(-7,2)", -7 / 2);
    show("int.rem(-7,2)", -7 % 2);

    // 2. 정수 범위: i64::MAX + 1 은 넘침. checked_add 는 넘치면 None
    let max_plus_1 = i64::MAX.checked_add(1);
    show("int.max_i64_plus_1", format!("{max_plus_1:?}"));

    // 3. 부동소수점 → 문자열
    show("float.str(1.0)", 1.0_f64);
    show("float.str(0.1+0.2)", 0.1_f64 + 0.2);
    show("float.str(1e16)", 1e16_f64);
    show("float.str(1e-7)", 1e-7_f64);
    show("float.str(-0.0)", -0.0_f64);
    show("float.str(nan)", f64::NAN);
    show("float.fmt2(0.125)", format!("{:.2}", 0.125_f64));
    show("float.fmt2(0.375)", format!("{:.2}", 0.375_f64));
    show("float.fmt2(2.675)", format!("{:.2}", 2.675_f64));
    show("float.round(0.5)", 0.5_f64.round());
    show("float.round(2.5)", 2.5_f64.round());

    // 4. 문자열 길이와 대소문자
    show("str.len(한글)", "한글".len());
    show("str.upper(straße)", "straße".to_uppercase());

    // 5. 문자열 → 정수
    show("parse(' 42 ')", try_int(" 42 "));
    show("parse('4_2')", try_int("4_2"));
    show("parse('+42')", try_int("+42"));
    show("parse('４２')", try_int("４２"));

    // 6. 해시 컬렉션 순회 순서
    let set: HashSet<&str> = ["apple", "banana", "cherry", "durian"].into();
    show("set.order", set.into_iter().collect::<Vec<_>>().join(" "));
    let map: HashMap<&str, i32> =
        [("apple", 1), ("banana", 2), ("cherry", 3), ("durian", 4)].into();
    show("dict.order", map.into_keys().collect::<Vec<_>>().join(" "));
}
