use std::io::Read;
use std::process::ExitCode;

const USAGE: &str = "usage: wordstats [--top N] [--min M] < input.txt";

fn parse_args() -> Result<(usize, usize), String> {
    let mut top = 5;
    let mut min = 1;
    let mut args = std::env::args().skip(1);
    while let Some(flag) = args.next() {
        let value = args.next().ok_or(format!("{flag} needs a value"))?;
        let number: usize = value
            .parse()
            .map_err(|_| format!("invalid number: {value}"))?;
        match flag.as_str() {
            "--top" => top = number,
            "--min" => min = number,
            _ => return Err(format!("unknown option: {flag}")),
        }
    }
    Ok((top, min))
}

fn main() -> ExitCode {
    let (top, min) = match parse_args() {
        Ok(v) => v,
        Err(msg) => {
            eprintln!("{USAGE}\nerror: {msg}");
            return ExitCode::from(2);
        }
    };
    let mut text = String::new();
    if let Err(e) = std::io::stdin().read_to_string(&mut text) {
        eprintln!("error: {e}");
        return ExitCode::from(1);
    }
    println!("{}", wordstats::summary(&text, top, min));
    ExitCode::SUCCESS
}
