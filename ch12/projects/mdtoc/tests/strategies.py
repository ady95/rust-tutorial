"""무작위 비교(fuzz)에 쓸 입력 생성 규칙. 12장 자동화 도구의 fuzz 하네스가 cases() 를 불러 쓴다.

사람이 Python 으로 쓰는 시험 자산이다. Markdown 의 경계(코드 블록, # 개수, 공백 종류, 줄 경계 문자,
Unicode 대소문자·단어 글자)를 섞은 문서를 만든다.
"""

from __future__ import annotations

from hypothesis import strategies as st

# 계약 2절·3절에서 Python 동작에 기대는 글자들
SPECIAL = ["\t", " ", "\xa0", "\u2003", "\u3000", "\x1c", "\x1f", "\x85", "\u2028", "\x0b", "\x0c", "\r",
           "#", "`", "~", "-", "_", "!", "\"", "\\", "\x01", "\x7f", "İ", "ẞ", "Σ", "ς", "Ⅻ", "½", "١", "가", "🎉",
           "\u0301", "\ufeff"]

word = st.text(alphabet=st.sampled_from(list("abcXYZ019 _-.") + SPECIAL), min_size=0, max_size=12)
any_text = st.text(min_size=0, max_size=12)

line = st.one_of(
    st.builds(lambda indent, hashes, sep, title, close: " " * indent + "#" * hashes + sep + title + close,
              st.integers(0, 4), st.integers(1, 7), st.sampled_from(["", " ", "\t", "  "]),
              st.one_of(word, any_text), st.sampled_from(["", " #", " ##  ", "#", " # "])),
    st.builds(lambda indent, mark, n, info: " " * indent + mark * n + info,
              st.integers(0, 4), st.sampled_from(["`", "~"]), st.integers(2, 5), st.sampled_from(["", " py", " a`b", "  "])),
    word,
)

newline = st.sampled_from(["\n", "\n", "\n", "\r\n", "\r", "\x85", "\u2028", "\x0b"])


@st.composite
def document(draw: st.DrawFn) -> str:
    lines = draw(st.lists(line, max_size=12))
    return "".join(text + draw(newline) for text in lines)


@st.composite
def cases(draw: st.DrawFn) -> dict:
    """{"args": [...], "stdin": bytes} 하나."""
    args: list[str] = []
    if draw(st.booleans()):
        args += ["--min-level", str(draw(st.integers(1, 3)))]
    if draw(st.booleans()):
        args += ["--max-level", str(draw(st.integers(3, 6)))]
    if draw(st.booleans()):
        args.append("--json")
    if draw(st.booleans()):
        args.append("--numbered")
    data = draw(document()).encode("utf-8")
    if draw(st.integers(0, 19)) == 0:
        data += b"\xff"  # 가끔 잘못된 UTF-8
    return {"args": args, "stdin": data}
