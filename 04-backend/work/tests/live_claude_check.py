"""실제 Claude API 시험 5회(대표 승인 2026-11-22: 대본 다듬기·요약·번역·브리핑·TTS 정규화, Haiku 5.5, 합계 $0.01 미만).
pytest가 모으지 않는 파일명이다. 서버 프로세스·포트 없이 앱을 프로세스 안에서 부른다(TestClient). 음성 엔진은 mock.
키는 server/.env 또는 환경변수에서 서버 코드가 읽는다. 이 스크립트는 키 값을 출력하지 않는다(있는지 여부만).
실행: .venv\\Scripts\\python -X utf8 tests\\live_claude_check.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

DATA = tempfile.mkdtemp(prefix="voicetool-live-")
os.environ.update(VOICETOOL_DATA_DIR=DATA, VOICETOOL_TTS_ENGINE="mock", VOICETOOL_STT_ENGINE="mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from server import app as appmod, claude, db  # noqa: E402

MAX_USD = 0.01


def main():
    if not claude.key_present():
        print("키 없음: server/.env 또는 환경변수 ANTHROPIC_API_KEY가 필요합니다. 호출하지 않고 끝냅니다.")
        return 2
    res = {}
    with TestClient(appmod.app, base_url="http://127.0.0.1:8000") as c:
        c.put("/api/settings", json={"limit_usd": MAX_USD})  # 시험 중 비용 상한(100%면 이후 호출 차단)

        def show(name, r):
            body = r.json()
            res[name] = {"status": r.status_code, "usage": body.get("usage"), "error": body.get("error")}
            print(f"[{name}] HTTP {r.status_code}", json.dumps(body, ensure_ascii=False)[:400])

        show("1 대본 다듬기", c.post("/api/script/refine", json={
            "text": "2026년 11월 신제품 출시 안내. 사전 예약 고객 1,284명에게 10% 할인 쿠폰을 드립니다.", "tone": "formal"}))
        show("4 브리핑", c.post("/api/summarize", json={
            "text": "3분기 매출 12억 3,400만 원(전년 대비 12.5% 증가). 신규 고객 320명. 광고비는 8% 줄었음. "
                    "4분기 목표는 매출 15억 원. 결정 필요: 연말 프로모션 예산 2천만 원 승인 여부.", "length": "short"}))
        # 2·3: 전사(mock 엔진, 12초 → 구간 3개) 뒤 요약·번역
        import wave
        src = Path(DATA) / "silence.wav"
        with wave.open(str(src), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000 * 12)
        jid = c.post("/api/transcribe", files={"file": ("시험.wav", src.read_bytes(), "audio/wav")}).json()["job_id"]
        tid = wait(c, jid)["result"]["transcript_id"]
        # mock 전사 문장은 의미가 없어 실제 회의 문장으로 바꿔 넣는다(시험 데이터, 임시 DB)
        segs = [{"start": 0.0, "end": 5.0, "text": "다음 주 월요일까지 견적서 수정본을 김 대리가 공유하기로 했습니다."},
                {"start": 5.0, "end": 10.0, "text": "자막은 영어와 일본어로 준비하는 걸로 정했어요."},
                {"start": 10.0, "end": 12.0, "text": "예산은 다음 회의에서 다시 보기로 했습니다."}]
        db.run("UPDATE transcripts SET segments=? WHERE id=?", json.dumps(segs, ensure_ascii=False), tid)
        show("2 요약", c.post(f"/api/transcripts/{tid}/summary"))
        tj = wait(c, c.post(f"/api/transcripts/{tid}/translate", json={"lang": "en"}).json()["job_id"])
        print("[3 번역] job", tj["status"], tj.get("error"))
        print(c.get(f"/api/transcripts/{tid}/srt?lang=en").text[:400])
        res["3 번역"] = {"status": tj["status"], "error": tj.get("error")}
        if "--skip-normalize" in sys.argv:  # 4회 시험(대본·브리핑·요약·번역)
            nj = None
        else:
            nj = wait(c, c.post("/api/tts", json={"text": "SEO 점수 72점, 1,284명 참여, 전년 대비 12.5% 증가.",
                                              "voice_id": "mock_tone", "title": "정규화 시험"}).json()["job_id"])
        if nj:
            o = next(x for x in c.get("/api/outputs").json() if x["id"] == nj["result"]["output_id"]) if nj["status"] == "done" else {}
            print("[5 정규화]", nj["status"], "|", o.get("normalizer"), "|", o.get("text_normalized"))
            res["5 정규화"] = {"status": nj["status"], "normalizer": o.get("normalizer"), "normalized": o.get("text_normalized")}
        rows = db.q("SELECT feature, input_tokens, cache_write_5m_tokens, cache_read_tokens, output_tokens, "
                    "stop_reason, status, latency_ms, cost_usd_est FROM usage_ledger WHERE engine='claude_api' ORDER BY ts")
        print("\n원장:")
        for r in rows:
            print(" ", r)
        total = sum(r["cost_usd_est"] for r in rows)
        print(f"Claude 호출 {len(rows)}회, 합계 추정 ${total:.6f} (상한 ${MAX_USD})")
        res["ledger"], res["total_usd"] = rows, total
    out = Path(__file__).resolve().parent / ("live_claude_result_4.json" if "--skip-normalize" in sys.argv else "live_claude_result.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("결과 저장:", out, "| 임시 데이터:", DATA)
    return 0


def wait(c, jid, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "canceled"):
            return j
        time.sleep(0.2)
    raise SystemExit(f"timeout {jid}")


if __name__ == "__main__":
    sys.exit(main())
