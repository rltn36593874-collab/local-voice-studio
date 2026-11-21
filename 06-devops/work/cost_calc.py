"""06-devops-infra.md §4 비용 재계산 (2026-11-21). 단가 출처는 문서 §3·§4 참조. 실행: python -I cost_calc.py"""
H = 730  # 월 시간

# 단가 (USD/h) — 확인값
AZ_KR = {"A100": 4.959, "A10": 4.32, "D2s": 0.118, "D4s": 0.236}   # Azure koreacentral
AZ_US = {"A100": 3.673, "A10": 3.2, "D2s": 0.096, "D4s": 0.192}    # Azure eastus
RUNPOD = {"L4": 0.69, "L40S": 1.09, "A100": 2.09}                   # Secure Cloud, 리전 미표기
DB, EDGE, QUEUE = 110, 5, 0          # Supabase Large, Workers Paid, Queues(무료 한도 안)
R2 = 0.015

def m(rate, n=1):
    return rate * H * n

# 물량 기본안 (01 §6-3 / 07 §5-3)
TTS_CHARS, STT_H = 17_120_000, 144
min_hi, min_lo = TTS_CHARS / 350, TTS_CHARS / 1000      # 한국어 350자/분[07 가정] ~ 1,000자/분[EL 영어]
tts_gpu_h = min_hi * 0.1228 / 60                          # CosyVoice2 스트리밍 동시1 RTF(가장 느린 값), L20
stt_gpu_h = STT_H / (13 * 60 / 16)                        # faster-whisper int8 batch8: 13분을 16초, 3070Ti
store_gb = (min_lo * 0.96 + STT_H * 57.6 + 480) / 1000, (min_hi * 0.96 + STT_H * 57.6 + 480) / 1000

common = DB + EDGE + QUEUE + 5  # 저장소 상한 $5
cpu_kr = m(AZ_KR["D2s"], 2) + m(AZ_KR["D4s"])
cpu_us = m(AZ_US["D2s"], 2) + m(AZ_US["D4s"])
fixed = {
    "KR A100x1": m(AZ_KR["A100"]) + cpu_kr + common,
    "KR A100x2": m(AZ_KR["A100"], 2) + cpu_kr + common,
    "US(Azure) A100x1": m(AZ_US["A100"]) + cpu_us + common,
    "OS L40Sx1": m(RUNPOD["L40S"]) + cpu_us + common,
    "OS L40Sx2": m(RUNPOD["L40S"], 2) + cpu_us + common,
    "OS L4x2": m(RUNPOD["L4"], 2) + cpu_us + common,
}
api = (TTS_CHARS / 1000 * 0.04 + STT_H * 0.20, TTS_CHARS / 1000 * 0.08 + STT_H * 0.20)

# PVC 1건: StyleTTS2 1h 데이터 50epoch = A100 4장 x 4h
pvc_gpu_h = 16
pvc = {n: (n * pvc_gpu_h * RUNPOD["A100"], n * pvc_gpu_h * AZ_KR["A100"]) for n in (1, 15, 128)}

# 손익분기 물량 용량 점검 (07 §9-2 v2 손익분기 MAU / 기본 MAU 5,000)
ACTIVE_H = 12 * 30.4          # 하루 12시간 활성 [가정]
PER_GPU_CONC = 3.5            # 첫 청크 ~500ms 기준 동시 3~4 (CosyVoice2 L20 벤치)
RTF_STREAM1, RTF_STREAM4 = 0.1228, 0.0741

def capacity(k, rtf=RTF_STREAM1):
    tts_h = min_hi * k * rtf / 60                     # 350자/분(보수적) 기준 GPU시간
    avg = tts_h / ACTIVE_H
    peak = avg + 2.33 * avg ** 0.5                    # ElevenLabs 추정식 99%
    gpus_latency = -(-peak // PER_GPU_CONC)           # 올림
    gpus_thru = -(-(tts_h + stt_gpu_h * k) // H)
    return tts_h, peak, int(max(gpus_latency, gpus_thru))

BE = {"해외 L4x2": 14_607, "해외 이중화": 20_665, "한국 이중화": 79_933}

if __name__ == "__main__":
    for name, mau in BE.items():
        k = mau / 5000
        h, p, g = capacity(k)
        h4, p4, g4 = capacity(k, RTF_STREAM4)
        print(f"{name}: x{k:.2f} TTS GPU-h {h:,.0f}(RTF.1228)/{h4:,.0f}(.0741) 피크동시 {p:.1f}/{p4:.1f} 필요GPU {g}/{g4} (+이중화 1)")
    print(f"TTS 분: {min_lo:,.0f}~{min_hi:,.0f} / TTS GPU-h 상한 {tts_gpu_h:.1f} / STT GPU-h {stt_gpu_h:.2f}")
    print(f"저장 증가 GB/월: {store_gb[0]:.1f}~{store_gb[1]:.1f}")
    print(f"CPU KR {cpu_kr:.2f} / US {cpu_us:.2f}")
    for k, v in fixed.items():
        print(f"{k}: {v:,.2f}")
    print(f"API 구매: {api[0]:,.2f}~{api[1]:,.2f}")
    for n, (a, b) in pvc.items():
        print(f"PVC {n}건: GPU-h {n*pvc_gpu_h}, RunPod {a:,.2f}, Azure KR {b:,.2f}")
    # 검산
    assert round(m(4.959), 2) == 3620.07 and round(cpu_kr, 2) == 344.56
    assert round(fixed["OS L40Sx2"], 2) == 1991.72
    assert tts_gpu_h < H * 0.2, "TTS 처리량은 GPU 1장의 20% 미만이어야 결론 유지"
    assert abs(api[0] - 713.6) < 0.01
    assert capacity(1)[2] == 1 and capacity(16)[2] >= 3, "기본안 1장, 16배면 3장 이상"

# ── 안 B 재산정 (01 §6-0 정본, 2026-11-21) ──────────────────────────
# (이름, 에이전트 분, STT 시간, 고품질 TTS 자, 피크 동시 통화)
B = [("3M 보수", 12_000, 1_127, 2_700_000, 5), ("3M 기본", 156_000, 14_651, 21_460_000, 29),
     ("3M 낙관", 336_000, 31_556, 47_420_000, 55), ("12M 기본", 480_000, 45_080, 64_380_000, 75),
     ("12M 낙관", 1_080_000, 101_430, 140_810_000, 155)]
SPEAK = 0.5        # 통화 중 에이전트 발화 비중: EL 스케일테스트 패턴(사용자 10초 / 재생 10초)
BATCH_UTIL = 0.7   # 배치 GPU 목표 사용률 [가정]
CALLS_PER_SIP_VM = 50  # D4s 1대당 동시 통화 [가정, LiveKit SIP 사이징 확인 못 함]
GPU = {"KR": AZ_KR["A100"] * H, "OS": RUNPOD["L40S"] * H}
D4 = {"KR": AZ_KR["D4s"] * H, "OS": AZ_US["D4s"] * H}

def ceil(x):
    return int(-(-x // 1))

def plan_b(agent_min, stt_h, tts_chars, peak_calls):
    g = peak_calls * SPEAK * RTF_STREAM1                     # 동시 생성 기대값
    rt = max(1, ceil((g + 2.33 * g ** 0.5) / PER_GPU_CONC)) + 1   # 실시간 풀(+예비 1)
    batch_h = tts_chars / 350 * RTF_STREAM4 / 60 + stt_h / (13 * 60 / 16)
    bt = max(1, ceil(batch_h / (H * BATCH_UTIL)))
    sip = ceil(peak_calls / CALLS_PER_SIP_VM)
    store = (stt_h * 57.6 + tts_chars / 350 * 0.96) / 1000   # GB/월, 30일 보관이면 상시 보관량
    def fixed(rt_reg, bt_reg):
        cpu = (cpu_kr if rt_reg == "KR" else cpu_us) + sip * D4[rt_reg]
        return rt * GPU[rt_reg] + bt * GPU[bt_reg] + cpu + DB + EDGE + store * R2
    var = agent_min * 0.0048 + agent_min * 0.0034          # 실시간 STT(Deepgram) + 전화(Twilio US 참고)
    return dict(rt=rt, bt=bt, batch_h=batch_h, sip=sip, store=store, var=var,
                KR=fixed("KR", "KR"), MIX=fixed("KR", "OS"), OS=fixed("OS", "OS"),
                api=tts_chars / 1000 * 0.08 + stt_h * 0.20 + agent_min * 0.08)

if __name__ == "__main__":
    for name, *v in B:
        r = plan_b(*v)
        print(f"{name}: 실시간GPU {r['rt']} 배치GPU {r['bt']}(GPU-h {r['batch_h']:,.0f}) SIP VM {r['sip']} 저장 {r['store']:,.0f}GB | "
              f"고정 KR {r['KR']:,.0f} MIX {r['MIX']:,.0f} OS {r['OS']:,.0f} | 변동 {r['var']:,.0f}+LLM | EL API {r['api']:,.0f}+LLM")
    r = plan_b(156_000, 14_651, 21_460_000, 29)
    assert r["rt"] == 3 and r["bt"] == 1, r          # 3M 기본: 실시간 2+예비1, 배치 1
