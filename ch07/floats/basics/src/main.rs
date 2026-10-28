//! float_basics.py 와 같은 계산을 Rust 의 흔한 방식으로 한다 (07-4).

fn main() {
    let tenths = [0.1_f64; 10];
    let naive: f64 = tenths.iter().sum();
    println!("sum([0.1]*10): {naive:?}");
    let cancel = [1e16, 1.0, -1e16];
    let s: f64 = cancel.iter().sum();
    println!("sum([1e16, 1.0, -1e16]): {s:?}");
    // 소수 둘째 자리 반올림을 흔히 이렇게 쓴다
    for x in [0.125_f64, 0.375, 2.675] {
        println!("round({x}, 2): {:?}", (x * 100.0).round() / 100.0);
    }
    for x in [1.0_f64, 1e16, 1e-5, 0.1 + 0.2, 123456789.0] {
        println!("display {x:e}: {x} / debug: {x:?}");
    }
    println!("format .4 of 0.00005: {:.4}", 0.00005_f64);
    println!("format .4 of 0.00015: {:.4}", 0.00015_f64);
}
