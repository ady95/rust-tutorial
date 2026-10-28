// Python 습관: 두 문자열 중 하나를 그대로 돌려준다
pub fn longer(a: &str, b: &str) -> &str {
    if b.chars().count() > a.chars().count() {
        b
    } else {
        a
    }
}
