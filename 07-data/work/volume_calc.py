"""기획팀 물량 가정(3안) -> 월 크레딧 -> 기능별 월 사용량 환산. 2026-11-21 데이터팀.
단가 근거: elevenlabs.io/pricing FAQ + 앱 /app/subscription/creative 비교표(UI 기준 크레딧).
[가정] 표시 값은 근거 없는 가정이다.
"""

PLAN_CREDITS = {"free": 10_000, "starter": 30_000, "creator": 121_000, "pro": 600_000}  # [확인]
PLAN_PRICE = {"starter": 6, "creator": 22, "pro": 99}  # USD/월, 월간 결제 [확인]
PAID_MIX = {"starter": 0.6, "creator": 0.3, "pro": 0.1}  # [가정] 데이터팀 제안
FEATURE_SHARE = {"tts": 0.60, "stt": 0.10, "music": 0.08, "sfx": 0.05, "vc_iso": 0.07, "dub": 0.10}  # [가정]
# 크레딧/단위 [확인]: TTS 1/자, STT 330/분, 뮤직 900/분, 효과음 200/생성, 보이스체인저·아이솔레이터 1,000/분, 자동더빙(워터마크) 2,000/분
UNIT = {"tts": 1, "stt": 330, "music": 900, "sfx": 200, "vc_iso": 1000, "dub": 2000}
SCENARIOS = {  # 기획팀 제안값: MAU, 유료 전환율, 소진율(무료, 유료)
    "보수": (1_000, 0.03, 0.20, 0.40),
    "기본": (5_000, 0.05, 0.30, 0.50),
    "낙관": (20_000, 0.08, 0.40, 0.60),
}

assert abs(sum(PAID_MIX.values()) - 1) < 1e-9 and abs(sum(FEATURE_SHARE.values()) - 1) < 1e-9
paid_avg_credits = sum(PLAN_CREDITS[p] * w for p, w in PAID_MIX.items())
paid_avg_price = sum(PLAN_PRICE[p] * w for p, w in PAID_MIX.items())
assert paid_avg_credits == 114_300 and round(paid_avg_price, 2) == 20.10

for name, (mau, conv, u_free, u_paid) in SCENARIOS.items():
    paid = mau * conv
    free_cr = (mau - paid) * PLAN_CREDITS["free"] * u_free
    paid_cr = paid * paid_avg_credits * u_paid
    total = free_cr + paid_cr
    vol = {f: total * s / UNIT[f] for f, s in FEATURE_SHARE.items()}
    print(f"[{name}] MAU {mau:,} 유료 {paid:,.0f}명 | 월 크레딧 {total:,.0f} (무료 {free_cr/total:.0%}) | 구독매출 ${paid*paid_avg_price:,.0f}")
    print(f"   TTS {vol['tts']/1e6:,.2f}M자 | STT {vol['stt']/60:,.0f}시간 | 뮤직 {vol['music']:,.0f}분 | "
          f"효과음 {vol['sfx']:,.0f}회 | VC·아이솔 {vol['vc_iso']:,.0f}분 | 더빙 {vol['dub']:,.0f}분")
