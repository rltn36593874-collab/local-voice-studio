"""사용량 원장과 비용 계산(07-data §5-2). 비용 식은 07-data claude_credit.py cost()와 같고, 장문·배치 분기를 더했다."""
from datetime import datetime

from . import db

M = 1_000_000


class UnknownModel(Exception):
    pass


def price_row(model_id):
    r = db.one("SELECT * FROM price_book WHERE model_id=? ORDER BY price_version DESC LIMIT 1", model_id)
    if not r:
        raise UnknownModel(model_id)
    return r


def cost(p, inp=0, w5=0, w1h=0, rd=0, out=0, batch=False):
    """p: price_book 행. 프롬프트(입력+캐시 쓰기+캐시 읽기)가 장문 기준을 넘으면 요청 전체에 장문 단가."""
    long_ = p.get("long_threshold") and (inp + w5 + w1h + rd) > p["long_threshold"]
    k = "long_" if long_ else ""
    usd = (inp * p[k + "inp"] + w5 * p[k + "w5"] + w1h * p[k + "w1h"] + rd * p[k + "rd"] + out * p[k + "out"]) / M
    return usd * (0.5 if batch else 1)


def record_claude(feature, job_id, resp, prompt_version, latency_ms, status="ok", model_id=None, is_batch=False):
    u = getattr(resp, "usage", None)
    cc = getattr(u, "cache_creation", None)
    w5 = (getattr(cc, "ephemeral_5m_input_tokens", 0) or 0) if cc else (getattr(u, "cache_creation_input_tokens", 0) or 0)
    w1h = (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0) if cc else 0
    row = dict(inp=getattr(u, "input_tokens", 0) or 0, w5=w5, w1h=w1h,
               rd=getattr(u, "cache_read_input_tokens", 0) or 0, out=getattr(u, "output_tokens", 0) or 0)
    model_id = model_id or getattr(resp, "model", None)
    p = price_row(model_id)
    usd = cost(p, **row, batch=is_batch)
    db.run("""INSERT INTO usage_ledger(entry_id,ts,request_id,job_id,feature,engine,model_id,prompt_version,is_batch,
              input_tokens,cache_write_5m_tokens,cache_write_1h_tokens,cache_read_tokens,output_tokens,stop_reason,
              status,latency_ms,price_version,cost_usd_est) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           db.new_id("use"), db.utcnow(), getattr(resp, "id", None), job_id, feature, "claude_api", model_id,
           prompt_version, int(is_batch), row["inp"], w5, w1h, row["rd"], row["out"], getattr(resp, "stop_reason", None),
           status, latency_ms, p["price_version"], usd)
    return {"input_tokens": row["inp"], "output_tokens": row["out"], "cache_read_tokens": row["rd"],
            "est_usd": round(usd, 6)}


def record_local(feature, job_id, engine, status, cpu_seconds, audio_in_sec=None, audio_out_sec=None, chars_in=None):
    db.run("""INSERT INTO usage_ledger(entry_id,ts,job_id,feature,engine,model_id,status,cpu_seconds,audio_in_sec,
              audio_out_sec,chars_in) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
           db.new_id("use"), db.utcnow(), job_id, feature, "local_cpu", engine, status, cpu_seconds,
           audio_in_sec, audio_out_sec, chars_in)


def month_key(dt=None):
    return (dt or datetime.now()).strftime("%Y-%m")


def month_summary(month=None):
    month = month or month_key()
    # ts는 UTC. 월 경계 몇 시간 차이는 사내 경고 용도라 허용한다. shortcut: UTC 월 기준, 정밀 대조는 export.csv로
    r = db.one("""SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o,
                  COALESCE(SUM(cache_read_tokens),0) rd,
                  COALESCE(SUM(cache_write_5m_tokens+cache_write_1h_tokens),0) w,
                  COALESCE(SUM(cost_usd_est),0) usd
                  FROM usage_ledger WHERE engine='claude_api' AND substr(ts,1,7)=?""", month)
    limit = db.get_setting("limit_usd")  # 대표 결정: 기본값 비움(None)
    warn = 0
    if limit:
        ratio = r["usd"] / limit
        warn = 100 if ratio >= 1 else 80 if ratio >= 0.8 else 0
    return {"month": month, "input_tokens": r["i"], "output_tokens": r["o"], "cache_read_tokens": r["rd"],
            "cache_write_tokens": r["w"], "est_usd": round(r["usd"], 4), "limit_usd": limit, "warn_level": warn}
