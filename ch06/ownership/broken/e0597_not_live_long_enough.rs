// Python 습관: 반복문 안에서 만든 값을 바깥 리스트에 모은 뒤 한꺼번에 쓴다
pub fn join_lower(lines: &[&str]) -> String {
    let mut out: Vec<&str> = Vec::new();
    for line in lines {
        let lower = line.to_lowercase();
        out.push(lower.as_str());
    }
    out.join(" ")
}
