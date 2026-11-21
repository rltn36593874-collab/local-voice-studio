// 팀 세션당 동시 서브에이전트 수 제한 hook.
// 사용법: node subagent-limit.js [max]   (기본 2)
// - PreToolUse(Agent|Task): 슬롯이 남아 있으면 예약, 꽉 차면 deny
// - SubagentStop / PostToolUseFailure(Agent|Task): 슬롯 반환
// 상태: ~/.claude/subagent-limit/<session_id>.json  (오래된 예약은 자동 만료)
const fs = require('fs');
const path = require('path');
const os = require('os');

const MAX = parseInt(process.argv[2] || '2', 10);
const STALE_MS = 3 * 60 * 60 * 1000; // 3시간 지난 예약은 누수로 보고 버림
const dir = path.join(os.homedir(), '.claude', 'subagent-limit');

function sleep(ms) { Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms); }

function withLock(file, fn) {
  const lock = file + '.lock';
  for (let i = 0; i < 100; i++) {
    try { fs.mkdirSync(lock); break; } catch (e) {
      try { if (Date.now() - fs.statSync(lock).mtimeMs > 10000) fs.rmdirSync(lock); } catch {}
      sleep(20);
    }
  }
  try { return fn(); } finally { try { fs.rmdirSync(lock); } catch {} }
}

function load(file) {
  try {
    const s = JSON.parse(fs.readFileSync(file, 'utf8'));
    const now = Date.now();
    s.slots = (s.slots || []).filter(t => now - t < STALE_MS);
    return s;
  } catch { return { slots: [] }; }
}

function save(file, s) { fs.writeFileSync(file, JSON.stringify(s)); }

let raw = '';
process.stdin.on('data', c => (raw += c));
process.stdin.on('end', () => {
  let ev;
  try { ev = JSON.parse(raw); } catch { process.exit(0); }
  const sid = ev.session_id;
  if (!sid) process.exit(0);
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, sid.replace(/[^\w-]/g, '_') + '.json');
  const event = ev.hook_event_name;
  const isAgentTool = ev.tool_name === 'Agent' || ev.tool_name === 'Task';

  if (event === 'PreToolUse' && isAgentTool) {
    const denied = withLock(file, () => {
      const s = load(file);
      if (s.slots.length >= MAX) { save(file, s); return s.slots.length; }
      s.slots.push(Date.now());
      save(file, s);
      return 0;
    });
    if (denied) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason:
            `팀 규칙: 서브에이전트는 동시에 최대 ${MAX}개까지만 허용됩니다 (현재 ${denied}개 실행 중). ` +
            `실행 중인 서브에이전트가 끝난 뒤 다시 시도하거나 직접 처리하세요.`,
        },
      }));
    }
    process.exit(0);
  }

  if (event === 'SubagentStop' || (event === 'PostToolUseFailure' && isAgentTool)) {
    withLock(file, () => {
      const s = load(file);
      s.slots.shift();
      save(file, s);
    });
    process.exit(0);
  }

  if (event === 'SessionStart' && ev.source === 'startup') {
    // 새 세션: 이 세션 파일 초기화 + 1일 지난 다른 세션 파일 정리
    try { fs.unlinkSync(file); } catch {}
    try {
      for (const f of fs.readdirSync(dir)) {
        const p = path.join(dir, f);
        if (Date.now() - fs.statSync(p).mtimeMs > 86400000) fs.rmSync(p, { recursive: true, force: true });
      }
    } catch {}
  }
  process.exit(0);
});
