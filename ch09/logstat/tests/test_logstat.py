from pathlib import Path

import pytest

from logstat import main, nearest_rank, run

FIXTURES = Path(__file__).parent / "fixtures"
HEADER = "ts,method,path,status,bytes,latency_ms\n"


def cli(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = main([*args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_basic_csv_text(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = cli(capsys, str(FIXTURES / "basic.csv"), "--top", "3")
    assert code == 0
    assert err == ""
    # 손으로 검산한 값: 쿼리를 뗀 /api/users 가 4건, 같은 2건은 경로 오름차순("/" < "/api/orders")
    assert out == (
        "records: 10\n"
        "skipped: 5\n"
        "range: 2026-10-29T09:00:01+00:00 .. 2026-10-29T09:01:31+00:00\n"
        "bytes: 4288\n"
        "status: 2xx=6 3xx=1 4xx=1 5xx=2\n"
        "methods: GET=8 DELETE=1 POST=1\n"
        "latency_ms: p50=15.75 p95=1200.0 p99=1200.0\n"
        "peak_minute: 2026-10-29T09:00Z 5\n"
        "top_paths:\n"
        "4\t25.0%\t30.25\t250.125\t/api/users\n"
        "2\t0.0%\t1e-05\t12.5\t/\n"
        "2\t50.0%\t80.5\t1200.0\t/api/orders\n"
    )


def test_csv_and_jsonl_give_same_summary(capsys: pytest.CaptureFixture[str]) -> None:
    _, csv_out, _ = cli(capsys, str(FIXTURES / "basic.csv"), "--json")
    _, jsonl_out, _ = cli(capsys, str(FIXTURES / "basic.jsonl"), "--json")
    assert csv_out.split(',"skipped"')[0] == jsonl_out.split(',"skipped"')[0]


def test_nearest_rank() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert [nearest_rank(values, p) for p in (50, 95, 99)] == [2.0, 4.0, 4.0]
    assert nearest_rank([7.0], 50) == 7.0


def test_query_string_is_dropped() -> None:
    text = HEADER + "2026-10-29T00:00:00Z,GET,/a?x=1,200,1,1\n2026-10-29T00:00:00Z,GET,/a?y=2,200,1,1\n"
    _, out, _ = run(text, "csv", 10, False, False)
    assert out.endswith("2\t0.0%\t1.0\t1.0\t/a\n")


def test_timezone_and_peak_minute() -> None:
    text = (HEADER + "2026-10-29T09:00:30+09:00,GET,/a,200,1,1\n2026-10-29T00:00:10Z,GET,/a,200,1,1\n"
            "2026-10-29T00:01:00Z,GET,/a,200,1,1\n")
    _, out, _ = run(text, "csv", 10, False, False)
    assert "range: 2026-10-29T00:00:10+00:00 .. 2026-10-29T00:01:00+00:00\n" in out
    assert "peak_minute: 2026-10-29T00:00Z 2\n" in out


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ('{"ts":"2026-10-29T00:00:00Z","method":"GET","path":"/","status":true,"bytes":1,"latency_ms":1}', "bad status"),
        ('{"ts":"2026-10-29T00:00:00Z","method":"GET","path":"/","status":200,"bytes":1,"latency_ms":NaN}', "bad latency_ms"),
        ('{"ts":"2026-02-30T00:00:00Z","method":"GET","path":"/","status":200,"bytes":1,"latency_ms":1}', "bad ts"),
        ('{"ts":"2026-10-29T00:00:00Z","method":"GET","path":"/","status":200,"bytes":1}', "missing field: latency_ms"),
        ("[1]", "not an object"),
        ("{", "invalid json"),
    ],
)
def test_strict_reasons(line: str, reason: str) -> None:
    assert run(line + "\n", "jsonl", 10, False, True) == (1, "", f"logstat: error: record 1: {reason}\n")


def test_huge_csv_field_rejects_file() -> None:
    text = HEADER + "2026-10-29T00:00:00Z,GET,/" + "x" * 131072 + ",200,1,1\n"
    assert run(text, "csv", 10, False, False) == (1, "", "logstat: error: record 1: csv field too large\n")


def test_empty_input_json() -> None:
    _, out, _ = run("", "csv", 10, True, False)
    assert out == ('{"records":0,"skipped":0,"first":null,"last":null,"bytes":0,'
                   '"status":{"2xx":0,"3xx":0,"4xx":0,"5xx":0},"methods":{},"latency_ms":null,'
                   '"peak_minute":null,"top_paths":[]}\n')


@pytest.mark.parametrize("args", [["x.log"], ["x.csv", "--top", "0"], ["x.csv", "--js"], ["x.csv", "--format", "tsv"]])
def test_usage_errors_exit_2(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert capsys.readouterr().err != ""
