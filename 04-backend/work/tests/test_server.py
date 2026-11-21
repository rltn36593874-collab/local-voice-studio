"""서버 시험: mock 엔진 + 가짜 Claude 클라이언트(실제 API 호출 없음).
실행: .venv\\Scripts\\python -m pytest -q tests"""
import json
import os
import sys
import tempfile
import time
import wave
from pathlib import Path
from types import SimpleNamespace as NS

TMP = tempfile.mkdtemp(prefix="voicetool-test-")
os.environ.update(VOICETOOL_ENV_FILE=str(Path(TMP) / "no.env"), VOICETOOL_DATA_DIR=TMP, VOICETOOL_TTS_ENGINE="mock", VOICETOOL_STT_ENGINE="mock",
                  VOICETOOL_FFMPEG_DIR=str(Path(TMP) / "no-ffmpeg"))
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server import app as appmod, claude, config, db, ledger  # noqa: E402

BASE = "http://127.0.0.1:8000"


@pytest.fixture(scope="module")
def c():
    with TestClient(appmod.app, base_url=BASE) as client:
        yield client


def wait(c, jid, timeout=20):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed", "canceled"):
            return j
        time.sleep(0.05)
    raise AssertionError(f"job {jid} timeout: {j}")


# ---------- 비용(07-data claude_credit.py assert 이식 + 장문·배치) ----------
def P(model):
    return {"inp": 0, "w5": 0, "w1h": 0, "rd": 0, "out": 0, "long_threshold": None, **model}


OPUS = P(dict(inp=4.00, w5=5.00, w1h=8.00, rd=0.20, out=20.00))
SONNET = P(dict(inp=2.00, w5=2.50, w1h=4.00, rd=0.10, out=10.00))


def test_cost_ported_from_07_data():
    assert abs(ledger.cost(OPUS, inp=50_000, out=15_000) - 0.50) < 1e-9
    assert abs(ledger.cost(OPUS, inp=10_000, rd=40_000, out=15_000) - 0.348) < 1e-9
    assert abs(ledger.cost(SONNET, inp=1_000_000, batch=True) - 1.0) < 1e-9
    assert abs(ledger.cost(SONNET, out=1_000_000, batch=True) - 5.0) < 1e-9


def test_cost_haiku_long_boundary(c):
    h = ledger.price_row("claude-haiku-5-5")
    assert abs(ledger.cost(h, inp=1000, out=1000) - (0.0001 + 0.0005)) < 1e-12
    # "over 100,000": 100,000은 일반, 100,001은 장문(캐시 읽기·쓰기 포함해서 셈)
    assert abs(ledger.cost(h, inp=90_000, rd=10_000) - (90_000 * 0.10 + 10_000 * 0.01) / 1e6) < 1e-12
    assert abs(ledger.cost(h, inp=90_001, rd=10_000) - (90_001 * 0.50 + 10_000 * 0.05) / 1e6) < 1e-12
    assert abs(ledger.cost(h, inp=200_000, out=1000, batch=True) - (200_000 * 0.50 + 1000 * 2.50) / 1e6 * 0.5) < 1e-12
    # 장문 배치 단가 = 0.25 / 1.25 (07-data 대조)
    assert abs(ledger.cost(h, inp=1_000_000, batch=True) - 0.25) < 1e-9
    with pytest.raises(ledger.UnknownModel):
        ledger.price_row("claude-unknown")


# ---------- 보안 ----------
def test_health_and_host_origin_guard(c):
    h = c.get("/api/health").json()
    assert h["ok"] and h["claude_key_present"] is False and h["ffmpeg"] is False
    assert TestClient(appmod.app, base_url="http://evil.example").get("/api/health").status_code == 403
    assert c.get("/api/health", headers={"Origin": "http://evil.example"}).status_code == 403
    assert c.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"}).status_code == 200
    assert c.get("/api/nope").json()["error"]["code"] == "not_found"


# ---------- TTS ----------
def test_tts_end_to_end(c):
    v = c.get("/api/voices").json()
    assert [x["id"] for x in v] == ["mock_tone"]
    r = c.post("/api/tts", json={"text": "안녕하세요. 사내 음성 도구 시험입니다! 두 번째 문장.", "voice_id": "mock_tone",
                                 "speed": 1.0, "format": "mp3", "title": "시험 낭독"})
    assert r.status_code == 202
    j = wait(c, r.json()["job_id"])
    assert j["status"] == "done", j
    assert j["created_at"] and j["finished_at"] and j["lane"] == "cpu" and j["title"] == "시험 낭독"
    outs = c.get("/api/outputs").json()
    o = next(x for x in outs if x["id"] == j["result"]["output_id"])
    assert o["files"] == {"wav": True}  # ffmpeg 없음 → wav만
    assert o["normalizer"] == "local(claude claude_key_missing)" and o["text"].startswith("안녕하세요")
    log = json.loads(db.one("SELECT detail FROM generation_log WHERE event='job_done' AND output_id=?", o["id"])["detail"])
    assert log["engine_version"] == "mock tone" and log["engine"] == "mock"
    assert o["disclosure_text"] == "※ 이 영상의 음성은 AI로 생성했습니다." and o["disclosure_required"] is True
    assert o["caption_text"] == "이 영상의 음성은 AI로 생성했습니다" and o["ai_notice"] == "start"
    assert o["ai_label"] and o["voice_name"] and o["duration_sec"] > 0
    full = c.get(f"/api/outputs/{o['id']}/audio")
    assert full.status_code == 200 and full.headers["content-type"] == "audio/wav"
    assert "AI 생성 음성".encode() in full.content  # WAV INFO 청크
    with wave.open(str(next(Path(TMP, "outputs").rglob("*_내레이션_시험-낭독_AI.wav")))) as w:
        assert w.getnframes() > 0  # 메타데이터를 붙여도 wav로 읽힌다
    part = c.get(f"/api/outputs/{o['id']}/audio", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100
    d = c.get(f"/api/outputs/{o['id']}/download?format=wav")
    assert "_AI.wav" in d.headers["content-disposition"]
    side = json.loads(next(Path(TMP, "outputs").rglob("*.ai.json")).read_text(encoding="utf-8"))
    assert side["ai_generated"] is True and side["job_id"] == j["id"]
    assert c.delete(f"/api/outputs/{o['id']}").json()["ok"]
    assert all(x["id"] != o["id"] for x in c.get("/api/outputs").json())
    lst = c.get("/api/jobs?active=1&recent=5").json()
    assert "active" in lst and any(x["id"] == j["id"] for x in lst["recent"])


def test_tts_validation(c):
    assert c.post("/api/tts", json={"text": "", "voice_id": "mock_tone"}).json()["error"]["code"] == "too_short"
    assert c.post("/api/tts", json={"text": "가" * 5001, "voice_id": "mock_tone"}).json()["error"]["code"] == "too_long"
    assert c.post("/api/tts", json={"text": "가", "voice_id": "nope"}).status_code == 404
    assert c.post("/api/tts", json={"text": "가", "voice_id": "mock_tone", "speed": 2}).status_code == 400


def test_cancel_queued(c):
    jid = db.new_id("job")  # 줄 스레드가 집기 전에 취소되게 직접 넣는다
    db.run("INSERT INTO jobs(id,type,lane,status,progress,payload,created_at) VALUES(?,?,?,?,?,?,?)",
           jid, "tts", "nolane", "queued", 0, "{}", db.now())
    assert c.delete(f"/api/jobs/{jid}").status_code == 202
    assert c.get(f"/api/jobs/{jid}").json()["status"] == "canceled"


# ---------- STT ----------
def test_transcribe_srt(c, tmp_path):
    src = tmp_path / "a.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000 * 12)
    r = c.post("/api/transcribe", files={"file": ("회의.wav", src.read_bytes(), "audio/wav")}, data={"language": "ko"})
    j = wait(c, r.json()["job_id"])
    assert j["status"] == "done", j
    t = c.get(f"/api/transcripts/{j['result']['transcript_id']}").json()
    assert len(t["segments"]) == 3 and t["source_name"] == "회의.wav" and t["source_expires_at"]
    srt = c.get(f"/api/transcripts/{t['id']}/srt?lang=ko").text
    assert srt.startswith("1\n00:00:00,000 --> 00:00:05,000\n")
    assert c.get(f"/api/transcripts/{t['id']}/srt?lang=en").status_code == 404
    assert c.post("/api/transcribe", files={"file": ("e.wav", b"", "audio/wav")}).json()["error"]["code"] == "too_short"


# ---------- Claude(가짜 클라이언트) ----------
class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        user = kw["messages"][0]["content"]
        if kw.get("output_config"):
            if "목표 언어" in user:
                items = [{"i": json.loads(l)["i"], "text": "EN " + json.loads(l)["text"]}
                         for l in user.split("\n\n", 1)[1].splitlines()]
                text = json.dumps({"items": items})
            else:
                text = json.dumps({"summary": "요약", "decisions": ["결정"], "todos": []})
        elif "음성 합성 전 정규화" in kw["system"][0]["text"]:
            text = user.replace("72점", "칠십이 점")  # 일부러 SEO는 남겨 로컬 안전망을 시험
        else:
            text = "다듬은 대본"
        return NS(id="msg_fake", model=kw["model"], stop_reason="end_turn",
                  content=[NS(type="text", text=text)],
                  usage=NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=600,
                           cache_creation_input_tokens=0,
                           cache_creation=NS(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=0)))


def test_claude_key_missing(c):
    r = c.post("/api/script/refine", json={"text": "원문"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "claude_key_missing"


def test_claude_features_and_ledger(c, monkeypatch, tmp_path):
    fake = NS(messages=FakeMessages())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(claude, "_client", fake)
    r = c.post("/api/script/refine", json={"text": "고유입력XYZ 안내", "tone": "formal"}).json()
    assert r["text"] == "다듬은 대본" and r["usage"]["cache_read_tokens"] == 600
    kw = fake.messages.calls[-1]
    assert kw["model"] == "claude-haiku-5-5" and kw["thinking"] == {"type": "disabled"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"} and "고유입력XYZ" not in kw["system"][0]["text"] and "고유입력XYZ" in kw["messages"][0]["content"]
    assert abs(r["usage"]["est_usd"] - (1000 * 0.10 + 600 * 0.01 + 200 * 0.50) / 1e6) < 1e-12
    row = db.one("SELECT * FROM usage_ledger WHERE feature='script' ORDER BY ts DESC LIMIT 1")
    assert row["prompt_version"] == "script.v1" and row["request_id"] == "msg_fake" and row["is_batch"] == 0
    assert "test-not-a-real-key" not in json.dumps(db.q("SELECT * FROM usage_ledger"))
    assert c.post("/api/summarize", json={"text": "보고서", "length": "short"}).json()["summary"] == "다듬은 대본"
    pdf = c.post("/api/summarize", files={"file": ("r.pdf", b"%PDF-1.4 fake", "application/pdf")}, data={"length": "short"})
    assert pdf.status_code == 200 and fake.messages.calls[-1]["messages"][0]["content"][0]["type"] == "document"
    assert c.post("/api/summarize", files={"file": ("r.docx", b"x", "application/octet-stream")}).status_code == 400
    # 전사 → 요약 → 번역(llm 줄)
    src = tmp_path / "b.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000 * 7)
    j = wait(c, c.post("/api/transcribe", files={"file": ("b.wav", src.read_bytes(), "audio/wav")}).json()["job_id"])
    tid = j["result"]["transcript_id"]
    s = c.post(f"/api/transcripts/{tid}/summary").json()
    assert s["summary"] == "요약" and s["decisions"] == ["결정"] and "usage" in s
    tj = wait(c, c.post(f"/api/transcripts/{tid}/translate", json={"lang": "en"}).json()["job_id"])
    assert tj["status"] == "done" and tj["lane"] == "llm" and tj["title"] == "영어 번역", tj
    assert j["title"] == "b.wav"
    srt = c.get(f"/api/transcripts/{tid}/srt?lang=en").text
    assert "EN (mock 전사 1)" in srt and "00:00:05,000 --> 00:00:07,000" in srt
    # 사용량·한도: 기본 null → 경고 없음 / 80% 경고 / 100% 정지
    u = c.get("/api/usage").json()
    assert u["limit_usd"] is None and u["warn_level"] == 0 and u["est_usd"] > 0
    spent = u["est_usd"]
    assert c.put("/api/settings", json={"limit_usd": spent / 0.85}).status_code == 200
    assert c.get("/api/usage").json()["warn_level"] == 80
    c.put("/api/settings", json={"limit_usd": spent / 2})
    r = c.post("/api/script/refine", json={"text": "원문"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "credit_limit"
    assert c.put("/api/settings", json={"limit_usd": None}).json() == {"limit_usd": None}
    csv_ = c.get("/api/usage/export.csv")
    assert csv_.status_code == 200 and "cost_usd_est" in csv_.text


def test_clone_not_yet(c):
    assert c.get("/api/consents/sentence").status_code == 501
    assert c.get("/api/consents").json() == []


def test_file_stem_no_overwrite(tmp_path):
    from datetime import datetime
    from server import audio
    w = datetime(2026, 11, 22, 9, 5, 7)
    s1 = audio.file_stem("보고 요약", False, "briefing", tmp_path, w)
    assert s1 == "20261122-0905_브리핑_보고-요약_AI"
    (tmp_path / f"{s1}.wav").write_bytes(b"x")
    assert audio.file_stem("보고 요약", False, "briefing", tmp_path, w) == "20261122-0905_브리핑_보고-요약-2_AI"


def test_env_file_loading(tmp_path, monkeypatch, capsys):
    secret = "test-dummy-key-not-real-0123456789"
    f = tmp_path / ".env"
    f.write_text("﻿# 주석\nOTHER=x\nANTHROPIC_API_KEY=\"" + secret + "\"\nbroken line\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.load_env_file(f) == ["ANTHROPIC_API_KEY"]
    assert os.environ["ANTHROPIC_API_KEY"] == secret and "OTHER" not in os.environ
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")  # 이미 있는 환경변수가 우선
    assert config.load_env_file(f) == [] and os.environ["ANTHROPIC_API_KEY"] == "from-shell"
    out = capsys.readouterr()
    assert secret[:8] not in out.out + out.err and secret[-6:] not in out.out + out.err


def test_normalize_qa_rules():
    from server.normalize import normalize as n
    assert n("1,284명이 참여") == "천이백팔십사 명이 참여"
    assert n("12.5% 증가") == "십이 점 오 퍼센트 증가"
    assert n("SEO 점수 72점") == "에스이오 점수 칠십이 점"
    assert n("3개, 25명, 20살, 100명, 10시") == "세 개, 스물다섯 명, 스무 살, 백 명, 열 시"
    assert n("1000원 10000원 15000원 100000000원") == "천 원 만 원 만오천 원 일억 원"
    assert n("YouTube 010") == "YouTube 공일공"  # 섞인 대소문자는 Claude 몫


def test_tts_claude_normalize_then_local(c, monkeypatch):
    fake = NS(messages=FakeMessages())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(claude, "_client", fake)
    c.put("/api/settings", json={"limit_usd": None})
    r = c.post("/api/tts", json={"text": "SEO 점수 72점, 1,284명 참여", "voice_id": "mock_tone", "title": "정규화"})
    j = wait(c, r.json()["job_id"])
    assert j["status"] == "done", j
    o = next(x for x in c.get("/api/outputs").json() if x["id"] == j["result"]["output_id"])
    assert o["text"] == "SEO 점수 72점, 1,284명 참여"
    assert o["text_normalized"] == "에스이오 점수 칠십이 점, 천이백팔십사 명 참여"
    assert o["normalizer"] == "claude:tts_normalize.v1+local"
    row = db.one("SELECT * FROM usage_ledger WHERE feature='tts_normalize' AND job_id=?", j["id"])
    assert row and row["cost_usd_est"] > 0


def test_normalize_guard_rejects_reorder():
    from server.normalize import suspicious
    raw = "SEO 점수 72점, 1,284명 참여, 전년 대비 12.5% 증가."
    assert suspicious(raw, "칠십이 점 에스이오 점수, 천이백팔십사 명 참여, 전년 대비 십이 점 오 퍼센트 증가.") == "reordered"
    assert suspicious(raw, "에스이오 점수 칠십이 점, 천이백팔십사 명 참여, 전년 대비 십이 점 오 퍼센트 증가.") is None
    assert suspicious("6월 10월 회의", "유월 시월 회의") is None  # 굳은 읽기로 바꾼 것은 통과
    assert suspicious("YouTube 영상 3개", "유튜브 영상 세 개") is None
    assert suspicious(raw, "요약.") == "length"


def test_disclosure_rules():
    from server import audio
    assert audio.disclosure("supertonic", False)["required"] is True
    assert audio.disclosure("melo", False)["required"] is True  # 법무 09 §2-3: 외부 공개물 전부
    d = audio.disclosure("melo", True, "홍길동 대표")
    assert d["caption_text"] == "AI로 복제한 홍길동 대표의 음성입니다"
    assert audio.notice_text(True, "홍길동 대표").startswith("이 음성은 AI로 복제한")


def test_tts_ai_notice_option(c):
    def dur(body):
        j = wait(c, c.post("/api/tts", json={"voice_id": "mock_tone", **body}).json()["job_id"])
        o = next(x for x in c.get("/api/outputs").json() if x["id"] == j["result"]["output_id"])
        return o
    on = dur({"text": "같은 문장입니다."})
    off = dur({"text": "같은 문장입니다.", "ai_notice": False})
    end = dur({"text": "같은 문장입니다.", "ai_notice_position": "end"})
    assert on["ai_notice"] == "start" and off["ai_notice"] is None and end["ai_notice"] == "end"
    assert on["duration_sec"] > off["duration_sec"] + 0.5  # 안내 + 0.5초 쉼이 붙었다
    assert c.post("/api/tts", json={"voice_id": "mock_tone", "text": "가", "ai_notice_position": "middle"}).status_code == 400


def test_pseudonymize_summary_and_translate(c, monkeypatch, tmp_path):
    fake = NS(messages=FakeMessages())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(claude, "_client", fake)
    c.put("/api/settings", json={"limit_usd": None, "pseudonym_names": ["홍길동"]})
    assert c.get("/api/settings").json()["pseudonym_names"] == ["홍길동"]
    src = tmp_path / "p.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(b"\0\0" * 16000 * 7)
    tid = wait(c, c.post("/api/transcribe", files={"file": ("p.wav", src.read_bytes(), "audio/wav")}).json()["job_id"])["result"]["transcript_id"]
    segs = [{"start": 0, "end": 5, "text": "김철수 대리가 010-1234-5678로 연락했고 홍길동도 왔다."},
            {"start": 5, "end": 7, "text": "메일은 kim@corp.co.kr 입니다."}]
    db.run("UPDATE transcripts SET segments=? WHERE id=?", json.dumps(segs, ensure_ascii=False), tid)
    r = c.post(f"/api/transcripts/{tid}/summary").json()
    sent = fake.messages.calls[-1]["messages"][0]["content"]
    assert "김철수" not in sent and "010-1234-5678" not in sent and "홍길동" not in sent and "kim@corp" not in sent
    assert "[이름1]" in sent and "[전화번호1]" in sent and r["pseudonymized"]["이름"] == 2
    tj = wait(c, c.post(f"/api/transcripts/{tid}/translate", json={"lang": "en"}).json()["job_id"])
    sent = fake.messages.calls[-1]["messages"][0]["content"]
    assert "010-1234-5678" not in sent and "[전화번호1]" in sent
    srt = c.get(f"/api/transcripts/{tid}/srt?lang=en").text
    assert "EN 김철수 대리가 010-1234-5678로" in srt and "kim@corp.co.kr" in srt  # 결과에서 원래 값으로 복원
    # 끄면 원문 그대로 보낸다
    c.post(f"/api/transcripts/{tid}/summary", json={"pseudonymize": False})
    assert "김철수" in fake.messages.calls[-1]["messages"][0]["content"]


def test_retention_voice_delete_and_purge(c):
    from datetime import datetime, timedelta
    from server import retention, secure
    vid, cid = "voice_t1", "con_t1"
    db.run("INSERT INTO voices VALUES(?,?,?,?,?,?,?)", vid, "대표 목소리", "홍길동 대표", cid, "openvoice", db.now(), None)
    cdir = Path(TMP, "consents", cid)
    cdir.mkdir(parents=True)
    (cdir / "read.wav").write_bytes(b"a")
    (cdir / "doc.pdf").write_bytes(b"d")
    db.run("INSERT INTO consents(id,owner_type,subject_name,recorded_at,audio_path,audio_sha256,doc_path,doc_sha256,voice_id) "
           "VALUES(?,?,?,?,?,?,?,?,?)", cid, "self", "홍길동 대표", db.now(), f"consents/{cid}/read.wav", "h1",
           f"consents/{cid}/doc.pdf", "h2", vid)
    secure.write(retention.secure_dir(vid) / "target_se.pth", b"embedding")
    retention.cache_dir(vid).mkdir(parents=True)
    (retention.cache_dir(vid) / "tmp.wav").write_bytes(b"x")
    assert secure.read(retention.secure_dir(vid) / "target_se.pth") == b"embedding"
    assert b"embedding" not in (retention.secure_dir(vid) / "target_se.pth.enc").read_bytes()  # 암호화되어 있다
    # 이 목소리로 만든 결과물을 게시
    oid = "out_t1"
    db.run("INSERT INTO outputs(id,kind,title,created_at,voice_id,voice_name,is_clone,consent_id,engine,files) "
           "VALUES(?,?,?,?,?,?,?,?,?,?)", oid, "tts", "t", db.now(), vid, "대표 목소리", 1, cid, "openvoice", "{}")
    assert c.put(f"/api/outputs/{oid}/publication", json={"published": True}).json()["published_at"]
    assert c.delete(f"/api/voices/{vid}").json()["ok"]
    assert not retention.secure_dir(vid).exists() and not retention.cache_dir(vid).exists()  # 즉시 삭제
    v = next(x for x in c.get("/api/consents").json() if x["id"] == cid)
    assert v["purge_at"] and v["record_purge_at"] is None  # 게시 중이면 동의 기록 계속 보관
    later = datetime.now().astimezone() + timedelta(days=366)
    retention.purge(later)
    con = db.one("SELECT * FROM consents WHERE id=?", cid)
    assert con and con["audio_purged_at"] and not (cdir / "read.wav").exists() and (cdir / "doc.pdf").exists()
    # 게시를 내리면 그로부터 1년 뒤 동의서·해시 삭제
    c.put(f"/api/outputs/{oid}/publication", json={"published": False})
    assert next(x for x in c.get("/api/consents").json() if x["id"] == cid)["record_purge_at"]
    retention.purge(datetime.now().astimezone() + timedelta(days=200))
    assert db.one("SELECT id FROM consents WHERE id=?", cid)  # 내린 지 1년이 안 됨
    retention.purge(later)
    assert db.one("SELECT id FROM consents WHERE id=?", cid) is None and not (cdir / "doc.pdf").exists()
    assert c.delete(f"/api/voices/{vid}").status_code == 404


def test_stt_quality_option(c, tmp_path):
    src = tmp_path / "q.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(bytes(2 * 16000 * 3))
    r = c.post("/api/transcribe", files={"file": ("q.wav", src.read_bytes(), "audio/wav")}, data={"quality": "draft"})
    payload = json.loads(db.one("SELECT payload FROM jobs WHERE id=?", r.json()["job_id"])["payload"])
    assert payload["model"] == "small" and payload["quality"] == "draft"
    r = c.post("/api/transcribe", files={"file": ("q.wav", src.read_bytes(), "audio/wav")})
    assert json.loads(db.one("SELECT payload FROM jobs WHERE id=?", r.json()["job_id"])["payload"])["model"] == "medium"
    assert c.post("/api/transcribe", files={"file": ("q.wav", src.read_bytes(), "audio/wav")},
                  data={"quality": "large"}).status_code == 400
    assert c.get("/api/health").json()["engines"]["stt"]["models"] == {"accurate": "medium", "draft": "small"}


def test_loudness_normalization(tmp_path):
    import array, math
    from server import audio
    p = tmp_path / "quiet.wav"
    a = array.array("h", (int(600 * math.sin(i / 10)) for i in range(16000)))
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(a.tobytes())
    g = audio.normalize_loudness(p, -20.0)
    with wave.open(str(p)) as w:
        b = array.array("h", w.readframes(w.getnframes()))
    rms_db = 20 * math.log10(math.sqrt(sum(x * x for x in b) / len(b)) / 32768)
    assert g > 10 and abs(rms_db + 20) < 0.5 and max(abs(x) for x in b) < 32767
