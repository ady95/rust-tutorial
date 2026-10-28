//! 비교용 "흔한" 이식 (07-4). 저자가 일부러 Python 의 세부 동작을 따르지 않고 쓴 버전이다.
//! 합계는 iter().sum(), 평균은 합/개수, 반올림은 100 을 곱해 round, 출력은 {:?}.

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() != 1 {
        eprintln!("usage: stats FILE");
        return ExitCode::from(2);
    }
    let Ok(text) = std::fs::read_to_string(&args[0]) else {
        eprintln!("stats: error: cannot read file: {}", args[0]);
        return ExitCode::from(1);
    };
    let mut numbers = Vec::new();
    for (i, line) in text.lines().enumerate() {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        match t.parse::<f64>() {
            Ok(x) => numbers.push(x),
            Err(_) => {
                eprintln!("stats: error: not a number on line {}: {t}", i + 1);
                return ExitCode::from(1);
            }
        }
    }
    if numbers.len() < 2 {
        eprintln!("stats: error: need at least 2 numbers");
        return ExitCode::from(1);
    }
    let n = numbers.len() as f64;
    let sum: f64 = numbers.iter().sum();
    let mean = sum / n;
    let var = numbers.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n - 1.0);
    let min = numbers.iter().copied().fold(f64::INFINITY, f64::min);
    let max = numbers.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    println!("count: {}", numbers.len());
    println!("sum: {sum:?}");
    println!("mean: {mean:?}");
    println!("mean2: {:?}", (mean * 100.0).round() / 100.0);
    println!("stdev: {:.4}", var.sqrt());
    println!("min: {min:?}");
    println!("max: {max:?}");
    ExitCode::SUCCESS
}
