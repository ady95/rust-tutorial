//! 06-4 실험용 추가 테스트. tests/spec.rs 의 normalize("Don't") == "don't" 와 충돌하므로
//! 어떤 코드로도 두 테스트를 함께 통과시킬 수 없다.

use wordstats::normalize;

#[test]
fn normalize_removes_inner_apostrophe() {
    assert_eq!(normalize("Don't"), "dont");
}
