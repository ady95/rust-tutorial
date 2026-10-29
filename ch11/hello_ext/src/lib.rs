//! 11-2: PyO3 확장 모듈의 기본. 호출 비용, 자료 변환 비용, 예외, GIL 해제를 보여 주는 작은 함수들.

#[pyo3::pymodule]
mod hello_ext {
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    /// 아무 일도 하지 않는 함수. Python → Rust 호출 한 번의 비용을 잰다.
    #[pyfunction]
    fn add(a: i64, b: i64) -> i64 {
        a + b
    }

    /// Python 리스트를 Vec<f64> 로 바꿔(복사) 더한다. 변환 비용이 계산보다 클 수 있다.
    #[pyfunction]
    fn sum_floats(values: Vec<f64>) -> f64 {
        values.iter().sum()
    }

    /// nearest-rank 백분위수(09장 logstat 과 같은 정의). 정렬 후 ceil(p*n/100)번째 값.
    #[pyfunction]
    fn percentile(mut values: Vec<f64>, p: u32) -> PyResult<f64> {
        if values.is_empty() {
            return Err(PyValueError::new_err("empty list"));
        }
        if values.iter().any(|v| v.is_nan()) {
            return Err(PyValueError::new_err("NaN in values"));
        }
        values.sort_by(|a, b| a.total_cmp(b));
        let k = (p as usize * values.len()).div_ceil(100).max(1);
        Ok(values[k - 1])
    }

    /// 공백으로 나눈 단어 수. 문자열을 빌려 쓰고(&str), 계산하는 동안 GIL 을 놓는다(다른 Python 스레드가 돌 수 있다).
    #[pyfunction]
    fn count_words(py: Python<'_>, text: &str) -> usize {
        py.detach(|| text.split_whitespace().count())
    }

    /// 계산 동안 GIL 을 잡고 있는 같은 함수(비교용).
    #[pyfunction]
    fn count_words_holding_gil(text: &str) -> usize {
        text.split_whitespace().count()
    }
}
