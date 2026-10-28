## Claude Code 전용 메모

- 이 세션에서는 셸 명령(Bash)을 쓸 수 없다. 검사는 훅이 대신 실행한다
- `.rs` 파일을 고칠 때마다 훅이 `cargo fmt` 와 `cargo check --all-targets` 를 실행하고, 오류가 있으면 그 결과를 알려 준다
- 작업을 끝내려 하면 훅이 `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` 를 실행한다. 실패하면 결과가 전달되니 고친 뒤 다시 끝낸다
