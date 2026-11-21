import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { useShell } from '../lib/shell.js'
import ResultCard from '../components/ResultCard.jsx'

const LEVEL_TEXT = {
  none: '',
  ok: '',
  warn: '월 상한의 80%를 넘었어요',
  over: '이번 달 Claude 한도에 닿았어요. 로컬 기능은 계속 쓸 수 있어요',
}

/** ⑤ 기록: 날짜별 결과(다시 듣기·내려받기·삭제) + 이번 달 Claude 사용량 */
export default function History({ active }) {
  const { usage, level, refreshUsage } = useShell()
  const [outs, setOuts] = useState([])
  const [limit, setLimit] = useState('')
  const [kind, setKind] = useState('all')
  const [consents, setConsents] = useState([])
  const [err, setErr] = useState('')

  const load = () => {
    api.listOutputs().then(setOuts, (e) => setErr(e.message))
    api.listConsents().then(setConsents, () => {})
  }
  // 이 화면이 보일 때마다 새로 읽는다(화면들은 숨겨진 채 살아 있음)
  useEffect(() => {
    if (active) load()
  }, [active])

  async function remove(o) {
    if (!confirm(`'${o.title}' 결과 파일을 삭제할까요? 생성 기록은 남아요.`)) return
    try {
      await api.deleteOutput(o.id)
      load()
    } catch (e) {
      setErr(e.message)
    }
  }

  async function saveLimit() {
    try {
      // 비우면 상한 없음(none)으로 돌아간다(디자인 02 §2-3)
      await api.saveSettings({ limit_usd: limit.trim() === '' ? null : Number(limit) })
      setLimit('')
      refreshUsage()
    } catch (e) {
      setErr(e.message)
    }
  }

  const shown = kind === 'all' ? outs : outs.filter((o) => o.kind === kind)
  const byDate = Object.groupBy(shown, (o) => o.created_at.slice(0, 10))

  return (
    <>
      <section className="card usage-card" id="usage">
        <h3>이번 달 Claude 사용량</h3>
        {usage ? (
          <>
            <p>
              <strong>${usage.est_usd.toFixed(2)}</strong>{usage.limit_usd > 0 ? ` / $${usage.limit_usd}` : ' · 상한 없음'} · 입력 {usage.input_tokens.toLocaleString()} · 출력{' '}
              {usage.output_tokens.toLocaleString()} · 캐시 읽기 {usage.cache_read_tokens?.toLocaleString() ?? 0} 토큰
            </p>
            {level !== 'none' && (
              <div className="usage-track" aria-hidden="true">
                <i style={{ '--pct': `${Math.min(100, (usage.est_usd / usage.limit_usd) * 100)}%` }} />
                <b style={{ left: '80%' }}><span>80%</span></b>
              </div>
            )}
            {LEVEL_TEXT[level] && <p className={level === 'over' ? 'error' : 'warn'} role="status">{LEVEL_TEXT[level]}</p>}
            <div className="row wrap">
              <label>
                월 상한($, 선택) <input className="field" type="number" min={0} step={1} value={limit} onChange={(e) => setLimit(e.target.value)} placeholder={usage.limit_usd > 0 ? String(usage.limit_usd) : '비우면 상한 없음'} />
              </label>
              <button className="btn" onClick={saveLimit}>저장</button>
              <span className="spacer" />
              <a className="btn btn-ghost" href={api.usageCsvUrl()} download={`claude-usage-${usage.month}.csv`}>원장 CSV</a>
            </div>
          </>
        ) : (
          <p className="muted">불러오는 중…</p>
        )}
      </section>

      {err && <p role="alert" className="error">{err}</p>}

      <div className="filters">
        <div className="seg" role="group" aria-label="종류">
          {[['all', '전체'], ['tts', '내레이션'], ['briefing', '브리핑'], ['transcript', '받아쓰기']].map(([v, l]) => (
            <button key={v} aria-pressed={kind === v} onClick={() => setKind(v)}>{l}</button>
          ))}
        </div>
      </div>

      {consents.length > 0 && (
        <section className="card">
          <h3>지운 목소리의 동의 기록</h3>
          {consents.map((c) => (
            <div key={c.id} className="voice-item">
              <span>{c.voice_name}</span>
              <span className="spacer" />
              <span className="faint">{c.purge_at.slice(0, 10)} 삭제 예정</span>
            </div>
          ))}
        </section>
      )}

      {shown.length === 0 ? (
        <section className="empty">
          <p>아직 만든 결과가 없어요.</p>
          <a className="btn btn-primary" href="#/tts">① 음성 만들기로</a>
        </section>
      ) : (
        Object.entries(byDate).map(([date, list]) => (
          <section key={date} className="card">
            <h3>{date}</h3>
            {list.map((o) => (
              <ResultCard key={o.id} output={o}>
                <button className="btn btn-danger btn-sm" onClick={() => remove(o)}>삭제</button>
              </ResultCard>
            ))}
          </section>
        ))
      )}
    </>
  )
}
