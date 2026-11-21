"""B2B 고객 유형별 1곳당 월 물량 × 고객 수 가설 (08-marketing-market.md §5).
근거·가정 표기는 문서 §5를 본다. 단가·고정비는 07-data §9 값을 참고로만 쓴다(정본은 데이터팀)."""

S = ("보수", "기본", "낙관")
WORKDAYS = 21  # 가정: 월 영업일

# --- AICC: 상담사 수 × 1인 월 콜 × AI 처리 비율 × 평균 통화 분 ---
CALLS_PER_AGENT = (580, 1000, 2500)   # LGU+ 계산 580 / 가정 중간 / 건보 120콜×21일≈2,500
AI_SHARE = (0.20, 0.30, 0.40)         # 농협~국민은행·KT 범위
AVG_MIN = (1.5, 2.0, 3.0)             # 가정: 보이스봇 평균 통화 분(공개값 없음)
STT_H_PER_AGENT = 161 * WORKDAYS / 60  # 다산콜 1인 하루 통화 161분 → 월 시간(녹취 전량 STT 시)

def aicc(agents, i):
    calls = agents * CALLS_PER_AGENT[i] * AI_SHARE[i]
    return {"agent_min": calls * AVG_MIN[i], "stt_h": agents * STT_H_PER_AGENT, "tts_chars": 0}

# --- 콘텐츠: 월 제작량 × 단위당 글자 수 ---
CHARS_PER_MIN = 300                    # 낭독 속도(자/분)
BOOK_CHARS = (6 * 60 + 37) * CHARS_PER_MIN   # 교보 예시 6시간37분 → 약 11.9만 자
ARTICLE_CHARS = 722.8                  # 조선일보 평균(2016 논문, 보도 기준)
BOOKS = (10, 50, 200)                  # 가정: 월 AI 제작 권수
ARTICLES_PER_DAY = (100, 300, 1000)    # 가정: 하루 변환 기사 수
ELEARN_HOURS = (10, 50, 200)           # 가정: 월 제작 음성 시간

def content(chars):
    return {"agent_min": 0, "stt_h": 0, "tts_chars": chars}

def per_customer(i):
    return {
        "AICC 중소(상담사 20명)": aicc(20, i),
        "AICC 중견(상담사 200명)": aicc(200, i),
        "오디오북 제작사·플랫폼": content(BOOKS[i] * BOOK_CHARS),
        "언론사(기사 듣기)": content(ARTICLES_PER_DAY[i] * ARTICLE_CHARS * 30),
        "이러닝·영상 제작사": content(ELEARN_HOURS[i] * 60 * CHARS_PER_MIN),
    }

# 고객 수 가설: (출시 3개월, 12개월) × 보수/기본/낙관
COUNTS = {
    "AICC 중소(상담사 20명)": ((1, 3, 8), (3, 10, 30)),
    "AICC 중견(상담사 200명)": ((0, 1, 2), (1, 3, 6)),
    "오디오북 제작사·플랫폼": ((0, 1, 2), (1, 3, 5)),
    "언론사(기사 듣기)": ((0, 1, 2), (1, 3, 6)),
    "이러닝·영상 제작사": ((3, 10, 25), (10, 30, 80)),
}

# 07-data §9 단가(원). 손익은 07 §9-5(GPU 반영)가 정본이라 여기서 고정비는 안 쓴다.
PRICE = {"agent_min": 75, "stt_h": 270, "tts_chars": 0.1}  # TTS 고품질 100원/1천 자

def totals(horizon, vol_i=1):
    """고객 수는 시나리오별, 1곳당 물량은 vol_i 고정(기본=1). 높은 값끼리 곱해 부풀리지 않으려는 것."""
    out = []
    for i in range(3):
        pc = per_customer(vol_i)
        t = {k: 0.0 for k in PRICE}
        for name, vol in pc.items():
            n = COUNTS[name][horizon][i]
            for k in t:
                t[k] += vol[k] * n
        rev = sum(t[k] * PRICE[k] for k in t)
        out.append((t, rev))
    return out

# 검산
assert BOOK_CHARS == 119_100
assert round(ARTICLE_CHARS * 1000 * 30) == 21_684_000          # 하위 조사 '월 약 2,170만 자'와 일치
assert round(STT_H_PER_AGENT, 1) == 56.4                        # 하위 조사 '약 57시간'과 일치
assert aicc(200, 1)["agent_min"] == 200 * 1000 * 0.3 * 2.0      # 12만 분
assert set(COUNTS) == set(per_customer(0))
assert totals(1)[1][0]["agent_min"] == 10 * 12_000 + 3 * 120_000  # 12개월 기본 = 중소10 + 중견3

if __name__ == "__main__":
    for i, s in enumerate(S):
        print(f"== 1곳당 월 물량 [{s}]")
        for name, v in per_customer(i).items():
            print(f"  {name}: 에이전트 {v['agent_min']:,.0f}분 · STT {v['stt_h']:,.0f}시간 · TTS {v['tts_chars']:,.0f}자")
    for h, label, vi in ((0, "출시 3개월", 1), (1, "출시 12개월", 1), (1, "민감도: 12개월, 1곳당 물량 보수값", 0)):
        print(f"== 합계 {label}")
        for i, (t, rev) in enumerate(totals(h, vi)):
            print(f"  {S[i]}: 에이전트 {t['agent_min']:,.0f}분 · STT {t['stt_h']:,.0f}시간 · TTS {t['tts_chars']:,.0f}자"
                  f" · 매출 {rev:,.0f}원")
