# 변형: 레코드를 해석하는 즉시 집계

출력은 그대로이고 집계 방식만 바꿨다.

## 바꾼 것
- `record.rs`
  - `Row` 타입을 없앴다.
  - `read_csv(text, sink) -> Option<String>`, `read_jsonl(text, sink)`: 행을 해석하는 즉시 `sink(레코드 번호, Result<Record, String>)` 을 부른다.
  - `read_csv` 의 반환값은 파일 전체를 거부하는 오류다. 그 앞 행들은 이미 `sink` 에 전달된 뒤다.
  - CSV·JSON 파서와 파일 전체 읽기는 그대로다.
- `lib.rs`
  - `summarize(&[Record], ..)` 를 없애고 `Aggregator`(`add(Record)`, `finish(top_n) -> Summary`)로 바꿨다.
  - `Aggregator` 가 누적하는 값: 개수, ts 최솟값·최댓값, `bytes` 합(u128), 상태 구간별 개수, 메서드별 개수, 분별 개수.
  - latency 는 전체용 `Vec<f64>` 와 경로별 `HashMap<Vec<u8>, PathStats{count, errors, latencies}>` 에만 모은다. 입력 순서를 지키므로 안정 정렬과 -0.0/0.0 순서는 그대로다.
  - `total_bytes` 를 없앴다. 해당 단위 테스트는 `Aggregator.bytes` 가 u64 를 넘어도 맞는지 보도록 고쳤다.
  - `run` 은 `Record` 목록 없이 `sink` 안에서 바로 `agg.add` 를 부른다.
- `--strict` 오류 우선순위
  - 첫 잘못된 레코드의 메시지만 `strict_error` 에 보관하고(그 뒤 레코드는 집계하지 않는다) 파일 끝까지 읽는다.
  - 헤더·`csv field too large` 오류가 있으면 그것을 먼저 돌려주고, 없을 때만 `strict_error` 를 돌려준다.
  - JSONL 은 오류 레코드가 있어도 끝까지 훑는다. 결과는 같고 오류 경로에서만 조금 느리다.

## 확인한 것(직접 실행)
- `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`(25개 통과), `cargo build --release`: 모두 통과.
- `automation/compare.py`: 27/27 일치.
- `automation/fuzz.py --examples 1500 --seed 20261029`: 일치.
- 기존 단위 테스트 `huge_field_beats_strict`(뒤의 긴 필드가 앞의 잘못된 레코드보다 우선)와 compare 의 `big-field` 가 통과했다.

## 확신하지 못하는 부분
- 메모리·속도는 측정하지 않았다. 경로별 latency 를 모두 보관하므로 경로 종류가 많은 입력에서는 `Vec` 이 많아진다. 백분위수에 필요한 값만 모으라는 요구에는 맞는다.
