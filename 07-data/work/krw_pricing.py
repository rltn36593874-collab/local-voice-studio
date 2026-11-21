"""포지셔닝 B(원화 종량제 한국어 음성 API) 단가안 + 손익분기. 2026-11-21 데이터팀 (v2: 06 §4.3 고정비표 반영).
전제(대표 잠정 결정): 크레딧 원화 가치는 모든 플랜 동일. 환율은 공개 시 서울외국환중개 매매기준율 전월 평균(분기 조정).
표기: [확인] 팀 문서/공개 페이지 값, [가정] 근거 없는 가정.
"""
FX = 1330.97          # [확인] KRW/USD, open.er-api.com 2026-11-20 집계값 — 공개 전 매매기준율 전월 평균으로 교체
FX_STRESS = 1460      # [가정] +10%
KRW_PER_CREDIT = 0.1  # [제안] 1크레딧 = 0.1원

PRICE = {  # [제안] 기능 -> (크레딧/단위, 단위)
    "tts_hq": (1.0, "자"), "tts_fast": (0.5, "자"),
    "stt_batch": (45, "분"), "stt_rt": (50, "분"), "agent": (750, "분"),
}
COMP_USD = {  # [확인] 08 §2-1·§4, 06 §4.3 (USD/단위)
    "tts_hq": {"EL v4·v3": 0.08 / 1000, "Typecast API(하단)": 0.07 / 1000},
    "tts_fast": {"EL Flash·v4 Turbo": 0.04 / 1000, "Google Chirp3 HD(무료 100만 자 후)": 30 / 1e6},
    "stt_batch": {"EL Scribe": 0.20 / 60, "Deepgram Nova-3": 0.0048, "OpenAI STT(하단)": 0.0045},
    "stt_rt": {"EL Realtime": 0.22 / 60},
    "agent": {"EL Agents": 0.08, "Cartesia Agents": 0.03},
}

# 고정비 [확인] 06 §4.3 (USD/월, 인건비·LLM·전화 기본료 제외). P0 = TTS + 파일 STT
FIXED_P0_USD = {"한국 최소": 4085, "한국 이중화": 7705, "해외 최소": 1196, "해외 이중화": 1992, "해외 L4×2": 1408}
# P1 에이전트 추가 고정비 [확인] 06 §4.5: 실시간 TTS GPU 1장
AGENT_FIXED_USD = {"한국": 3620, "해외": 796}
PG_FEE = 0.03                 # [가정] 결제 수수료율
STORAGE_USD_MONTH = 0.8       # [확인] 06 §4.4 저장 증가분 상한(월). GPU 시간은 고정비에 흡수(06 §4.4)
RT_STT_USD_MIN = 0.0048       # [확인] 06 §4.5 실시간 STT 상용 API(Deepgram)
PHONE_USD_MIN = 0.0034        # [확인] 미국 Twilio 착신 참고값. 국내 SIP 확인 못 함(06 §4.6)

def unit_krw(f):
    return PRICE[f][0] * KRW_PER_CREDIT

def var_cost_krw(f, fx=FX):
    """단위(1자 또는 1분)당 변동비. P0 기능은 결제 수수료만, 에이전트는 실시간 STT·전화 추가."""
    v = unit_krw(f) * PG_FEE
    if f == "agent":
        v += (RT_STT_USD_MIN + PHONE_USD_MIN) * fx
    return v

def cm_krw(f, fx=FX):
    return unit_krw(f) - var_cost_krw(f, fx)

# 기획 물량 3안(07 §5-3, 01 §6) — 유료 사용자 크레딧(ElevenLabs 단위)과 B 범위 비중
PAID_EL_CREDITS = {"보수": 30 * 114_300 * 0.40, "기본": 250 * 114_300 * 0.50, "낙관": 1600 * 114_300 * 0.60}
MAU = {"보수": 1000, "기본": 5000, "낙관": 20000}
TTS_SHARE, STT_SHARE, FAST_RATIO = 0.60, 0.10, 0.5   # [가정] 07 §5-2, 저지연 비중 50%

def p0_cm(name, fx=FX):
    tts = PAID_EL_CREDITS[name] * TTS_SHARE
    stt_min = PAID_EL_CREDITS[name] * STT_SHARE / 330
    rev = tts * (1 - FAST_RATIO) * unit_krw("tts_hq") + tts * FAST_RATIO * unit_krw("tts_fast") + stt_min * unit_krw("stt_batch")
    cm = tts * (1 - FAST_RATIO) * cm_krw("tts_hq", fx) + tts * FAST_RATIO * cm_krw("tts_fast", fx) + stt_min * cm_krw("stt_batch", fx)
    return rev, cm - STORAGE_USD_MONTH * fx

# ---- v3: GPU 대수를 물량에 맞춰 늘린다 (06 §4.8 capacity() 규칙을 그대로 옮김) ----
H = 730
ACTIVE_H = 12 * 30.4                  # [가정 06] 하루 12시간 활성
PER_GPU_CONC = 3.5                    # [06] 첫 청크 ~500ms 기준 GPU 1장당 동시 생성
RTF_SLOW = 0.1228                     # [04 §6.5] CosyVoice2 스트리밍 동시 1, L20 (가장 느린 값)
KO_CPM = 350                          # [가정] 한국어 자/분(보수)
# 구성: (GPU 1장 월 USD, GPU 외 월 USD, 이중화 예비 장수) [06 §4.3 분해]
CONFIG = {"해외 최소(L40S)": (1.09 * H, 400, 0), "해외 이중화(L40S)": (1.09 * H, 400, 1),
          "해외 L4": (0.69 * H, 400, 1), "한국 이중화(A100)": (4.959 * H, 465, 1)}

def stream_gpus(tts_chars):
    """실시간·스트리밍 TTS: 피크 동시 생성으로 필요한 GPU(서비스용)."""
    gpu_h = tts_chars / KO_CPM * RTF_SLOW / 60
    avg = gpu_h / ACTIVE_H
    peak = avg + 2.33 * avg ** 0.5
    return max(1, -(-peak // PER_GPU_CONC), -(-gpu_h // H)), gpu_h

def consumer_breakeven(cfg, name="기본", fx=FX):
    """MAU 경로: 손익분기 MAU ↔ GPU 대수 반복. TTS 부하는 무료 포함 전체 사용자, 매출은 유료만."""
    gpu_usd, other, spare = CONFIG[cfg]
    total_tts_per_mau = {"보수": 3_311_600, "기본": 28_537_500, "낙관": 183_328_000}[name] * TTS_SHARE / MAU[name]
    cm_per_mau = p0_cm(name, fx)[1] / MAU[name]
    mau, n = MAU[name], 1
    for _ in range(50):
        n = int(stream_gpus(total_tts_per_mau * mau)[0]) + spare
        new = (n * gpu_usd + other) * fx / cm_per_mau
        if abs(new - mau) < 1:
            break
        mau = new
    return mau, n, (n * gpu_usd + other)

# 08 §5-4 B2B 합계 [확인 08, 가정 기반 추정] : (에이전트 분, STT 시간, 고품질 TTS 자)
B2B = {
    "3개월 보수": (12_000, 1_127, 2_700_000), "3개월 기본": (156_000, 14_651, 21_460_000),
    "3개월 낙관": (336_000, 31_556, 47_420_000), "12개월 보수": (156_000, 14_651, 21_460_000),
    "12개월 기본": (480_000, 45_080, 64_380_000), "12개월 낙관": (1_080_000, 101_430, 140_810_000),
}

# 06 §4.9 [정본] 안 B 물량별 월 고정비 USD (GPU 대수·실시간 예비 1장 반영, 인건비·LLM 제외): (전부 한국, 혼합, 전부 해외)
FIXED_B2B_USD = {
    "3개월 보수": (11_493, 8_669, 2_924), "3개월 기본": (15_126, 12_301, 3_732), "3개월 낙관": (22_554, 16_905, 5_479),
    "12개월 보수": (15_126, 12_301, 3_732),  # 물량이 3개월 기본과 같음(08 §5-4)
    "12개월 기본": (26_186, 17_713, 6_287), "12개월 낙관": (44_683, 27_737, 10_598),
}
REGIONS = ("전부 한국", "혼합", "전부 해외")
# 실시간 GPU 장수: C = 06 §4.9(99% 피크 여유 + 예비 1, 06 권고) / A = 평균 동시 생성 ÷ 3.5(여유·예비 없음, 07 v3)
RT_GPUS_C = {"3개월 보수": 2, "3개월 기본": 3, "3개월 낙관": 4, "12개월 보수": 3, "12개월 기본": 4, "12개월 낙관": 6}
RT_GPUS_A = {"3개월 보수": 1, "3개월 기본": 1, "3개월 낙관": 1, "12개월 보수": 1, "12개월 기본": 2, "12개월 낙관": 3}
RT_GPU_USD = {"전부 한국": 4.959 * 730, "혼합": 4.959 * 730, "전부 해외": 1.09 * 730}  # 실시간 풀 리전 [06 §4.3 단가]

def b2b_pnl(name, fx=FX, rt="C"):
    agent_min, stt_h, tts_chars = B2B[name]
    rev = agent_min * unit_krw("agent") + stt_h * 60 * unit_krw("stt_batch") + tts_chars * unit_krw("tts_hq")
    var = agent_min * var_cost_krw("agent", fx) + stt_h * 60 * var_cost_krw("stt_batch", fx) + tts_chars * var_cost_krw("tts_hq", fx)
    cut = 0 if rt == "C" else RT_GPUS_C[name] - RT_GPUS_A[name]  # A안은 06 고정비에서 실시간 GPU 차이만큼 뺌
    return rev, var, {r: (usd - cut * RT_GPU_USD[r]) * fx for r, usd in zip(REGIONS, FIXED_B2B_USD[name])}

if __name__ == "__main__":
    assert abs(unit_krw("tts_hq") * 1000 - 100) < 1e-9 and abs(unit_krw("agent") - 75) < 1e-9
    assert stream_gpus(0)[0] == 1
    # 06 §4.9 변동비(실시간 STT + 전화)와 같은지 검산: 3개월 기본 156,000분 → $1,279
    assert round(156_000 * (RT_STT_USD_MIN + PHONE_USD_MIN)) == 1279
    assert all(0 < var_cost_krw(f) < unit_krw(f) * 0.2 for f in PRICE)
    print("== 단가안 (원) vs 경쟁가 (원 환산)")
    for f, (cr, u) in PRICE.items():
        per = 1000 if u == "자" else 1
        comp = ", ".join(f"{k} {v * FX * per:,.1f}" for k, v in COMP_USD[f].items())
        print(f"{f}: {unit_krw(f) * per:,.1f}원/{'1천 자' if per == 1000 else u} | 변동비 {var_cost_krw(f) * per:,.2f} | 경쟁 {comp}")

    print("\n== P0 기획 물량 손익 (월, 원) — 행: 물량안, 열: 고정비 구성")
    for n in PAID_EL_CREDITS:
        rev, cm = p0_cm(n)
        cells = " | ".join(f"{k} {cm - usd * FX:+,.0f}" for k, usd in FIXED_P0_USD.items())
        print(f"[{n}] 매출 {rev:,.0f} 공헌 {cm:,.0f} || {cells}")

    print("\n== P0 손익분기 (월) — 같은 전환·소진율일 때 MAU / 단일 기능 물량")
    for k, usd in FIXED_P0_USD.items():
        for fx in (FX, FX_STRESS):
            fixed = usd * fx
            mau = " ".join(f"{n}율 {fixed / (p0_cm(n, fx)[1] / MAU[n]):,.0f}" for n in MAU)
            print(f"[{k}|{fx:,.0f}] 고정비 {fixed:,.0f} | 손익분기 MAU: {mau} | 고품질 TTS {fixed / cm_krw('tts_hq', fx) / 1e6:,.1f}M자 "
                  f"| 저지연 {fixed / cm_krw('tts_fast', fx) / 1e6:,.1f}M자")

    print("\n== P1 에이전트 추가분 손익분기 (추가 고정비 ÷ 분당 공헌, LLM·국내 전화 기본료 제외)")
    for k, usd in AGENT_FIXED_USD.items():
        fixed = (usd + 0) * FX
        print(f"[{k}] 추가 고정비 {fixed:,.0f} | 분당 공헌 {cm_krw('agent'):,.1f} | 손익분기 {fixed / cm_krw('agent'):,.0f}분/월")

    print("\n== v3-A 소비자(MAU) 경로: GPU 대수를 반영한 손익분기 수렴값")
    for cfg in CONFIG:
        for n in MAU:
            mau, g, usd = consumer_breakeven(cfg, n)
            print(f"[{cfg}|{n}율] 손익분기 MAU {mau:,.0f} | GPU {g}장 | 고정비 ${usd:,.0f}")

    print("\n== v4 B2B 경로 (물량 08 §5-4 · 01 §6-0, 고정비 06 §4.9)")
    for k in FIXED_B2B_USD:
        for rt in ("C", "A"):
            for fx in (FX, FX_STRESS):
                rev, var, fixed = b2b_pnl(k, fx, rt)
                cells = " | ".join(f"{r} 고정 {f:,.0f} → {rev - var - f:+,.0f}" for r, f in fixed.items())
                print(f"[{k}|실시간 {rt}|{fx:,.0f}] 매출 {rev:,.0f} 변동 {var:,.0f} || {cells}")
