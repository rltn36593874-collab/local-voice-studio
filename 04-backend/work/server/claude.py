"""Claude 호출 래퍼 — 모든 Claude 호출이 지나는 한 곳(설계 §4).
Haiku 5.5, thinking 끔(effort 기본 medium이라 허용), 기능별 고정 시스템 프롬프트에만 cache_control.
API 키는 환경변수 ANTHROPIC_API_KEY에서만 읽고, 어디에도 쓰지 않는다."""
import json
import os
import re
import time

from . import config, ledger


class ClaudeError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


_client = None


def key_present():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def client():
    global _client
    if not key_present():
        raise ClaudeError("claude_key_missing", "Claude API 키가 설정되지 않았어요(환경변수 ANTHROPIC_API_KEY)", 503)
    if _client is None:
        os.environ.pop("ANTHROPIC_LOG", None)  # SDK 디버그 로그(요청 내용 출력)를 켜지 않는다
        import anthropic
        # 키를 명시적으로 넘긴다: SDK 기본 생성자가 다른 인증 경로(프로필)를 찾지 않게 하려는 것
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=2)
    return _client


def load_prompt(feature):
    """prompts/{feature}.v{N}.md 중 가장 높은 버전."""
    best = None
    for p in config.PROMPTS.glob(f"{feature}.v*.md"):
        m = re.fullmatch(rf"{re.escape(feature)}\.v(\d+)\.md", p.name)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), p)
    if not best:
        raise ClaudeError("config_error", f"프롬프트 파일이 없어요: {feature}", 500)
    return best[1].read_text(encoding="utf-8"), f"{feature}.v{best[0]}"


def guard_limit():
    s = ledger.month_summary()
    if s["warn_level"] >= 100:
        raise ClaudeError("credit_limit", "이번 달 Claude 사용 한도에 닿았어요. 설정에서 한도를 바꾸거나 다음 달까지 기다려 주세요", 402)


def call(feature, content, job_id=None, max_tokens=4000, schema=None):
    """content: 문자열 또는 content 블록 목록. schema가 있으면 구조화 출력으로 받아 dict를 돌려준다.
    반환: (text 또는 dict, usage dict)"""
    guard_limit()
    model = config.CLAUDE_MODEL
    ledger.price_row(model)  # 단가표에 없는 모델이면 호출 전에 막는다(07-data 합의)
    system_text, version = load_prompt(feature)
    c = client()
    import anthropic
    kw = dict(model=model, max_tokens=max_tokens, thinking={"type": "disabled"},
              system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
              messages=[{"role": "user", "content": content}])
    if schema:
        kw["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    t0 = time.monotonic()
    try:
        resp = c.messages.create(**kw)
    except anthropic.AuthenticationError:
        raise ClaudeError("claude_key_missing", "Claude API 키가 올바르지 않아요", 503)
    except anthropic.RateLimitError:
        raise ClaudeError("claude_error", "Claude 요청이 많아 잠시 막혔어요. 조금 뒤 다시 시도해 주세요")
    except anthropic.APIStatusError as e:
        raise ClaudeError("claude_error", f"Claude 오류({e.status_code}): {getattr(e, 'message', '')}"[:300])
    except anthropic.APIConnectionError:
        raise ClaudeError("claude_error", "Claude에 연결할 수 없어요. 인터넷 연결을 확인해 주세요")
    latency = int((time.monotonic() - t0) * 1000)
    status = "ok" if resp.stop_reason in ("end_turn", "stop_sequence") else "failed"
    usage = ledger.record_claude(feature, job_id, resp, version, latency, status=status, model_id=model)
    if resp.stop_reason == "refusal":
        raise ClaudeError("claude_refusal", "Claude가 이 내용의 처리를 거절했어요. 내용을 바꿔 다시 시도해 주세요", 422)
    if resp.stop_reason == "max_tokens":
        raise ClaudeError("claude_truncated", "결과가 너무 길어 잘렸어요. 입력을 나눠 주세요", 422)
    text = "".join(b.text for b in resp.content if b.type == "text")
    if schema:
        try:
            return json.loads(text), usage
        except json.JSONDecodeError:
            raise ClaudeError("claude_error", "Claude 응답 형식이 올바르지 않아요")
    return text, usage
