"""받아쓰기 결과를 Claude(해외)로 보내기 전 로컬 가명처리(법무 09 §5 L4, 대표 지시 2026-11-22).
사람 이름·전화번호·이메일·주민등록번호·계좌번호 패턴을 [이름1] 같은 표시로 바꾸고, Claude 결과에서 원래 값으로 되돌린다.
이름은 (a) 설정에 등록한 이름 목록, (b) '성+이름+호칭/직함' 패턴으로 찾는다.
shortcut: 이름 인식은 규칙 기반이라 호칭 없이 단독으로 나온 이름은 놓칠 수 있다. 놓치는 이름은 설정의 이름 목록에 더한다."""
import re

SURNAMES = ("김이박최정강조윤장임한오서신권황안송류유전홍고문양손배백허남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경")
TITLES = ("님", "씨", "대리", "과장", "차장", "부장", "팀장", "실장", "사장", "대표", "이사", "상무", "전무", "주임", "사원",
          "선생님", "선생", "교수", "원장", "본부장", "센터장", "매니저", "책임", "선임", "수석", "변호사", "회계사")

KINDS = [  # (표시 이름, 정규식) — 긴 패턴부터
    ("주민번호", re.compile(r"\d{6}\s?-\s?[1-8]\d{6}")),
    ("이메일", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("전화번호", re.compile(r"(?<!\d)(?:\+82[-\s]?)?0\d{1,2}[-\s.]?\d{3,4}[-\s.]?\d{4}(?!\d)")),
    ("계좌번호", re.compile(r"(?<!\d)\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,6})?(?!\d)")),
]
_title_alt = "|".join(sorted(TITLES, key=len, reverse=True))
NAME_RE = re.compile(rf"(?<![가-힣])([{SURNAMES}][가-힣]{{1,2}}|[{SURNAMES}])(\s?)(?=(?:{_title_alt}))")
# 성씨 글자로 시작하는 흔한 낱말(호칭 앞에 와도 이름이 아님)
STOP = {"이번", "이전", "이후", "이제", "정말", "정도", "조금", "전체", "전부", "주요", "우리", "고객", "오늘", "신규", "신입",
        "한번", "한편", "안녕", "문제", "공식", "기존", "기타", "현재", "원래", "장기", "차기", "지난", "지금", "모든", "모두",
        "성공", "진짜", "최근", "최고", "방금", "이상", "이하", "전임", "후임", "신임", "부"}


def _real(kind, v):
    """계좌번호 패턴은 날짜(2026-11-22)·짧은 번호와 겹치므로 숫자 10자리 이상만 계좌로 본다."""
    return kind != "계좌번호" or sum(c.isdigit() for c in v) >= 10


class Pseudonymizer:
    """한 문서(전사 하나) 단위로 같은 값에는 같은 표시를 준다. 대응표는 메모리에만 두고 저장하지 않는다."""

    def __init__(self, names=()):
        self.fwd, self.back, self.count = {}, {}, {}
        self.names = sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True)

    def _tag(self, kind, value):
        if value not in self.fwd:
            self.count[kind] = self.count.get(kind, 0) + 1
            tag = f"[{kind}{self.count[kind]}]"
            self.fwd[value], self.back[tag] = tag, value
        return self.fwd[value]

    def mask(self, text):
        for kind, rx in KINDS:
            text = rx.sub(lambda m: self._tag(kind, m.group(0)) if _real(kind, m.group(0)) else m.group(0), text)
        for n in self.names:
            text = re.sub(rf"(?<![가-힣A-Za-z]){re.escape(n)}", lambda m: self._tag("이름", m.group(0)), text)
        return NAME_RE.sub(lambda m: m.group(0) if m.group(1) in STOP else self._tag("이름", m.group(1)) + m.group(2), text)

    def unmask(self, obj):
        """문자열·리스트·딕셔너리 안의 표시를 원래 값으로 되돌린다."""
        if isinstance(obj, str):
            return re.sub(r"\[(?:이름|전화번호|이메일|주민번호|계좌번호)\d+\]", lambda m: self.back.get(m.group(0), m.group(0)), obj)
        if isinstance(obj, list):
            return [self.unmask(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.unmask(v) for k, v in obj.items()}
        return obj

    def stats(self):
        return dict(self.count)
