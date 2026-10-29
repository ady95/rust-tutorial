//! `f"{x:.1f}"` 표기(port/rust_reference/src/output.rs 에서 가져옴).
//! repr(float) 과 JSON 문자열은 Python 이 만들므로(경계가 float 객체다) 여기에는 없다.

/// `f"{errors / n * 100:.1f}%"`. 계산 순서(나눗셈 후 곱셈)를 바꾸지 않는다.
pub fn error_rate(errors: usize, n: usize) -> String {
    format!("{:.1}%", errors as f64 / n as f64 * 100.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rate_rounds_half_even() {
        assert_eq!(format!("{:.1}", 0.125), "0.1");
        assert_eq!(format!("{:.1}", 12.25), "12.2");
        assert_eq!(error_rate(1, 3), "33.3%");
        assert_eq!(error_rate(0, 3), "0.0%");
    }
}
