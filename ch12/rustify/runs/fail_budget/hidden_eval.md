# 숨긴 평가 (2026-10-30, 실행이 끝난 뒤 사람이 따로 실행)

mdtoc_s2 의 에이전트가 만든 verify/ 스크립트 세 개를 이 실행 파일(fail_budget)과 mdtoc_s2 에 똑같이 돌렸다.
스크립트는 작업 폴더의 xverify/ 에 복사해 실행했다. 맥락별 원인은 examples/probe_contexts.py 로 찾았다.

| 검사 | mdtoc_s2 | fail_budget |
|---|---|---|
| exhaustive_codepoints (1,112,064 코드 포인트 × 15 맥락, 500개씩 2,225 묶음) | 다른 묶음 0 | 다른 묶음 2,212 |
| slug_numbered (7,452건) | 0 | 0 |
| args_diff 깊이 3 (8,421 인자 목록) | 0 | 24 |

fail_budget 의 차이(probe_contexts.py):

- 맥락 `## a{c}Σ`: 1,105,088 코드 포인트. 예: 제목 "a" + U+0000 + "Σ" 의 앵커가 Python 은 "aσ", Rust 는 "aς".
  Python lower() 의 어말 시그마 규칙은 Σ 앞의 글자가 대소문자 무시 글자(case-ignorable)가 아니면 거기서 멈추는데,
  이 구현은 사이의 글자를 건너뛰고 "a" 를 보아 어말로 판정했다
- 맥락 `# x #{c}`, `# x {c}#{c}`: Σ 한 글자에서 같은 원인
- 인자: 위치 인자 다음에 옵션과 `--` 가 오는 목록(예: `a --json --`)에서 Python 은 사용법 오류(2), Rust 는 0 또는 1
