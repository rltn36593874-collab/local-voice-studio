"""TTS 앞단 정규화의 로컬 규칙(QA 4규칙). Claude 정규화 뒤 안전망으로 항상 한 번 더 돌고, Claude를 못 쓸 때는 단독으로 쓴다.
① 숫자→한글(천 단위 쉼표 제거) ② %→퍼센트 ③ 대문자 영문 약어→한글 읽기 ④ 숫자+단위 → '수사 단위'(띄어 씀)"""
import re

DIG = "영일이삼사오육칠팔구"
SMALL = ["", "십", "백", "천"]
BIG = ["", "만", "억", "조", "경"]
LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   ["에이", "비", "씨", "디", "이", "에프", "지", "에이치", "아이", "제이", "케이", "엘", "엠", "엔", "오",
                    "피", "큐", "알", "에스", "티", "유", "브이", "더블유", "엑스", "와이", "지"]))
LETTERS["Z"] = "제트"
# 고유어 수사로 읽는 단위(1~99). 그 밖은 한자어(1,284명 → 천이백팔십사 명: QA 예시)
NATIVE_UNITS = ("개", "명", "살", "시", "번", "마리", "잔", "권", "장", "대", "곳", "가지", "사람", "병", "벌", "켤레")
N_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
N_TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]


def sino(n: int) -> str:
    """정수 → 한자어 읽기. 0=영, 1000=천, 10000=만, 1억=일억."""
    if n == 0:
        return "영"
    out, g = [], 0
    while n:
        n, part = divmod(n, 10000)
        if part:
            s = ""
            for i, d in enumerate(f"{part:04d}"):
                d = int(d)
                pos = 3 - i
                if d:
                    s += ("" if d == 1 and pos else DIG[d]) + SMALL[pos]
            if g == 1 and part == 1 and not n:  # 맨 앞 '일만'은 '만'
                s = ""
            out.append(s + BIG[g])
        g += 1
    return "".join(reversed(out))


def native(n: int) -> str:
    """1~99 고유어 관형형(한, 두, 세, 스무)."""
    t, o = divmod(n, 10)
    return ("스무" if t == 2 and o == 0 else N_TENS[t]) + N_ONES[o]


def read_number(num: str) -> str:
    num = num.replace(",", "")
    if "." in num:
        a, b = num.split(".", 1)
        return sino(int(a or 0)) + " 점 " + "".join(DIG[int(c)] for c in b)
    if len(num) > 1 and num.startswith("0"):  # 0으로 시작하는 번호는 한 자리씩
        return "".join("공" if c == "0" else DIG[int(c)] for c in num)
    return sino(int(num))


NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_unit_re = re.compile(rf"({NUM})\s*(%|퍼센트|[가-힣]+)?")
_acr_re = re.compile(r"(?<![A-Za-z])[A-Z]{1,6}(?![a-z])")


def _num_sub(m):
    num, unit = m.group(1), m.group(2)
    if unit in ("%", "퍼센트"):
        return read_number(num) + " 퍼센트"
    if unit:
        u = next((x for x in NATIVE_UNITS if unit.startswith(x)), None)
        plain = num.replace(",", "")
        if u and "." not in plain and 1 <= int(plain) <= 99:
            return native(int(plain)) + " " + unit
        return read_number(num) + " " + unit
    return read_number(num)


def normalize(text: str) -> str:
    text = _acr_re.sub(lambda m: "".join(LETTERS[c] for c in m.group(0)), text)
    text = _unit_re.sub(_num_sub, text)
    return re.sub(r"[ \t]{2,}", " ", text)


def _words(t):
    return re.findall(r"[가-힣A-Za-z0-9]+", t)


def suspicious(raw: str, llm: str) -> str | None:
    """Claude 정규화 결과 검사(2026-11-22 실측: 'SEO 점수 72점' → '칠십이 점 에스이오 점수'로 어순이 바뀐 사례).
    로컬 규칙 결과와 단어 단위로 비교해 (1) 같은 단어가 자리를 옮겼거나 (2) 길이가 크게 달라지면 이유를 돌려준다."""
    from collections import Counter
    from difflib import SequenceMatcher
    a, b = _words(normalize(raw)), _words(llm)
    if not a:
        return None
    la, lb = len("".join(a)), len("".join(b))  # 글자 수로 비교(로컬 규칙은 단위를 띄어 써서 낱말 수가 늘어난다)
    if not 0.6 <= lb / la <= 1.6:
        return "length"
    common = sum((Counter(a) & Counter(b)).values())
    matched = sum(m.size for m in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return "reordered" if matched < common else None


def needs_fix(text: str) -> bool:
    return bool(re.search(r"\d|%|[A-Z]", text))
