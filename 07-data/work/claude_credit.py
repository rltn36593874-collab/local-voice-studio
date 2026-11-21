# Claude API 기능별 호출 1회 비용 추정 (문서 기준, 실제 API 호출 없음)
# 단가 출처: https://platform.claude.com/docs/en/about-claude/pricing (2026-11-21 조회)
# 실행: python -I -X utf8 claude_credit.py > claude_credit_out.txt

M = 1_000_000
# $/MTok: in, 5분 캐시 쓰기, 1시간 캐시 쓰기, 캐시 읽기, out
PRICE = {
    "haiku-5-5":  dict(inp=0.10, w5=0.125, w1h=0.20, rd=0.01, out=0.50),   # 프롬프트 10만 토큰 이하
    "sonnet-5-5": dict(inp=2.00, w5=2.50,  w1h=4.00, rd=0.10, out=10.00),
    "opus-5-5":   dict(inp=4.00, w5=5.00,  w1h=8.00, rd=0.20, out=20.00),
}
BATCH = 0.5          # 배치: 입력·출력 50% 할인, 캐시 배수와 중첩 (pricing 문서)
FX = 1330.97         # 원/달러, 1단계와 같은 집계값(공식 고시 아님). 사내 예산 감 잡기용
KO_TOK_PER_CHAR = 1.0  # [가정] 한국어 1자 ≈ 1토큰. count_tokens 실측 전 값
KO_CHARS_PER_MIN = 350  # [가정] 1단계와 같은 낭독 속도


def cost(model, inp=0, w5=0, rd=0, out=0, batch=False):
    p = PRICE[model]
    usd = (inp * p["inp"] + w5 * p["w5"] + rd * p["rd"] + out * p["out"]) / M
    return usd * (BATCH if batch else 1)


# 검산: pricing 문서 Managed Agents 예시(토큰분만). Opus 5.5 50k 입력 + 15k 출력 = $0.50
assert abs(cost("opus-5-5", inp=50_000, out=15_000) - 0.50) < 1e-9
# 같은 예시에서 40k가 캐시 읽기면 0.04 + 0.008 + 0.30 = $0.348
assert abs(cost("opus-5-5", inp=10_000, rd=40_000, out=15_000) - 0.348) < 1e-9
# 배치 단가표와 일치: Sonnet 5.5 배치 $1 / $5
assert abs(cost("sonnet-5-5", inp=M, batch=True) - 1.0) < 1e-9
assert abs(cost("sonnet-5-5", out=M, batch=True) - 5.0) < 1e-9

min_tok = KO_CHARS_PER_MIN * KO_TOK_PER_CHAR  # 1분 분량 한국어 토큰

# 기능 정의 (호출 1회 단위). sys=캐시 가능한 고정 접두(시스템·규칙·용어집·도구), var=매번 바뀌는 입력,
# out=응답, think=thinking 토큰(출력 단가로 과금). 모두 [가정]
FEATURES = [
    # 키, 이름, 단위, 추천 모델, sys, var, out, think, 배치 가능
    ("dub",   "더빙 번역",                "원본 10분",   "sonnet-5-5", 2_000, 10 * min_tok + 1_000, int(10 * min_tok * 1.2), 1_000, True),
    ("script", "대본·팟캐스트 원고",       "원고 10분",   "sonnet-5-5", 1_500, 2_500, int(10 * min_tok), 3_000, True),
    ("norm",  "발음 정규화·오디오 태그",   "텍스트 1천 자", "haiku-5-5", 2_500, int(1_000 * KO_TOK_PER_CHAR), int(1_150 * KO_TOK_PER_CHAR), 0, True),
    ("stt",   "STT 교정",                 "전사 10분",   "haiku-5-5",  2_000, 10 * min_tok, 10 * min_tok, 0, True),
    ("sfx",   "효과음·음악 프롬프트",       "프롬프트 1개", "haiku-5-5",  1_000, 100, 150, 0, False),
]
# 대안 모델(품질 우선일 때)
ALT = {"dub": "opus-5-5", "script": "opus-5-5", "norm": "sonnet-5-5", "stt": "sonnet-5-5", "sfx": "sonnet-5-5"}


def feature_costs(model, sys, var, out, think, batchable):
    o = out + think
    nocache = cost(model, inp=sys + var, out=o)
    cached = cost(model, rd=sys, inp=var, out=o)          # 고정 접두가 이미 캐시에 있을 때(5분 안 반복)
    first = cost(model, w5=sys, inp=var, out=o)           # 그 묶음의 첫 호출(캐시 쓰기)
    bc = cost(model, rd=sys, inp=var, out=o, batch=True) if batchable else None
    return nocache, first, cached, bc


def agent_call(model, turns=10, sys=4_000, new_per_turn=160, out=100, think=0):
    """에이전트 통화 1건(약 5분, 10턴). 자동 캐시: 매 턴 이전 대화까지 읽고 새 부분만 씀."""
    nocache = cached = 0.0
    for k in range(1, turns + 1):
        prefix = sys + new_per_turn * (k - 1)
        nocache += cost(model, inp=prefix + new_per_turn, out=out + think)
        if k == 1:
            cached += cost(model, w5=prefix + new_per_turn, out=out + think)
        else:
            cached += cost(model, rd=prefix, w5=new_per_turn, out=out + think)
    return nocache, cached


# 사용자 확정(directives 2026-11-21): 대표 1명, Haiku 위주 + 캐싱. 월 건수와 토큰은 모두 [가정]
# 이름, 1건 단위, 1건당 호출 수(초안 + 수정), sys, var, out, think, 월 건수(낮음, 기본, 높음)
SCENARIOS = [
    ("영상 내레이션 대본", "3분 영상 1편", 3, 1_500, 800, int(3 * min_tok), 500, (4, 8, 20)),
    ("받아쓰기 요약", "녹음 30분 1건", 1, 1_500, int(30 * min_tok), 800, 0, (10, 20, 40)),
    ("자막 번역", "영상 10분 × 1개 언어", 1, 2_000, int(10 * min_tok) + 1_000, int(10 * min_tok * 1.2) + 1_000, 0, (4, 8, 20)),
    ("보고서 음성 브리핑 원고", "보고서 → 3분 원고", 2, 1_500, 5_000, int(3 * min_tok), 0, (10, 22, 40)),
]


def scenario_cost(model, calls, sys, var, out, think):
    """1명이 띄엄띄엄 쓰므로 건마다 첫 호출은 캐시 쓰기, 5분 안 수정 호출만 캐시 읽기로 본다."""
    first = cost(model, w5=sys, inp=var, out=out + think)
    rest = cost(model, rd=sys, inp=var, out=out + think) * (calls - 1)
    return first + rest


def won(usd):
    return usd * FX


if __name__ == "__main__":
    print("== 에이전트 대화 (통화 1건 = 10턴, 시스템·도구 4,000토큰, 턴당 새 입력 160·출력 100) ==")
    rows = {}
    for m, think in (("haiku-5-5", 0), ("sonnet-5-5", 0), ("sonnet-5-5", 200)):
        nc, c = agent_call(m, think=think)
        rows[(m, think)] = (nc, c)
        print(f"{m:11s} think={think:3d}  캐시없음 ${nc:.5f} ({won(nc):.2f}원)  캐시 ${c:.5f} ({won(c):.2f}원)  절감 {1 - c / nc:.0%}")
    # 자동 캐시가 캐시 없음보다 싸야 한다(10턴이면 쓰기 할증을 읽기 할인이 넘는다)
    assert all(c < nc for nc, c in rows.values())

    print("\n== 기능별 호출 1회 (단위는 표 참고) ==")
    print("기능 | 단위 | 모델 | 입력(접두+가변) | 출력(+thinking) | 캐시없음 | 첫 호출 | 캐시 | 캐시+배치")
    for key, name, unit, m, sys, var, out, think, b in FEATURES:
        for model in (m, ALT[key]):
            nc, f, c, bc = feature_costs(model, sys, int(var), int(out), think, b)
            assert c <= nc  # 캐시 읽기는 기본 입력보다 싸다
            if bc is not None:
                assert abs(bc - c * BATCH) < 1e-12
            bcs = f"${bc:.5f} ({won(bc):.2f}원)" if bc is not None else "해당 없음"
            tag = "추천" if model == m else "대안"
            print(f"{name} | {unit} | {model}({tag}) | {sys}+{int(var)} | {int(out)}+{think} | "
                  f"${nc:.5f} ({won(nc):.2f}원) | ${f:.5f} | ${c:.5f} ({won(c):.2f}원) | {bcs}")

    print("\n== 사용자 확정 4개 시나리오: 대표 1명, Haiku 위주 + 캐싱 (월) ==")
    print("시나리오 | 1건 단위 | 1건 호출 수 | 월 건수(낮음/기본/높음) | 1건 비용 Haiku | 월 비용 Haiku(낮음/기본/높음) | 기본안 Sonnet 비교")
    tot = {"low": 0.0, "base": 0.0, "high": 0.0, "sonnet_base": 0.0}
    tok = {"in": 0, "out": 0}
    for name, unit, calls, sys, var, out, think, vol in SCENARIOS:
        per_h = scenario_cost("haiku-5-5", calls, sys, int(var), int(out), think)
        per_s = scenario_cost("sonnet-5-5", calls, sys, int(var), int(out), think if think else 500)
        m = {k: per_h * v for k, v in zip(("low", "base", "high"), vol)}
        for k in m:
            tot[k] += m[k]
        tot["sonnet_base"] += per_s * vol[1]
        tok["in"] += calls * (sys + int(var)) * vol[1]
        tok["out"] += calls * (int(out) + think) * vol[1]
        print(f"{name} | {unit} | {calls} | {vol[0]}/{vol[1]}/{vol[2]} | ${per_h:.5f} ({won(per_h):.1f}원) | "
              f"${m['low']:.3f}/${m['base']:.3f}/${m['high']:.3f} ({won(m['low']):,.0f}/{won(m['base']):,.0f}/{won(m['high']):,.0f}원) | "
              f"${per_s * vol[1]:.2f}")
    print(f"합계 Haiku: 낮음 ${tot['low']:.3f} / 기본 ${tot['base']:.3f} / 높음 ${tot['high']:.3f} "
          f"({won(tot['low']):,.0f} / {won(tot['base']):,.0f} / {won(tot['high']):,.0f}원)")
    print(f"같은 기본안을 Sonnet 5.5로 하면: ${tot['sonnet_base']:.2f} ({won(tot['sonnet_base']):,.0f}원) = Haiku의 {tot['sonnet_base'] / tot['base']:.0f}배")
    print(f"기본안 월 토큰: 입력 {tok['in']:,} / 출력 {tok['out']:,}")
    print(f"크레딧 $5·$10·$50로 버티는 개월(기본안 Haiku): "
          f"{5 / tot['base']:,.0f} / {10 / tot['base']:,.0f} / {50 / tot['base']:,.0f}개월")
    assert tot["low"] < tot["base"] < tot["high"] < tot["sonnet_base"]

    print("\n== 1달러로 가능한 횟수 (추천 모델, 캐시 적용) ==")
    nc, c = rows[("haiku-5-5", 0)]
    print(f"에이전트 통화(Haiku): {1 / c:,.0f}건")
    for key, name, unit, m, sys, var, out, think, b in FEATURES:
        _, _, c, _ = feature_costs(m, sys, int(var), int(out), think, b)
        print(f"{name}({unit}): {1 / c:,.0f}회")
