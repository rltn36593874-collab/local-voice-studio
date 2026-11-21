import { useState } from 'react'
import { api } from '../lib/api.js'
import { useShell } from '../lib/shell.js'
import SpeechMaker from '../components/SpeechMaker.jsx'

/** ③ 보고서 브리핑: 붙여넣기·파일(.txt .md .pdf) → Claude 요약(수정 가능) → 로컬 음성 */
export default function Briefing() {
  const { level, refreshUsage } = useShell()
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [length, setLength] = useState('short')
  const [summary, setSummary] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setBusy(true)
    setErr('')
    try {
      const r = await api.summarize({ text, file, length })
      setSummary(r.summary)
      refreshUsage()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <section className="card">
        <label className="block">
          보고서 붙여넣기
          <textarea className="field" rows={6} value={text} onChange={(e) => setText(e.target.value)} disabled={!!file} />
        </label>
        <div className="row wrap">
          <label>
            또는 파일 <input type="file" accept=".txt,.md,.pdf" onChange={(e) => setFile(e.target.files[0] ?? null)} />
          </label>
          {file && <button className="btn btn-ghost" onClick={() => setFile(null)}>파일 빼기</button>}
          <div className="seg" role="group" aria-label="요약 길이">
            {[['short', '짧게'], ['medium', '보통']].map(([v, l]) => (
              <button key={v} aria-pressed={length === v} onClick={() => setLength(v)}>
                {l}
              </button>
            ))}
          </div>
          <span className="spacer" />
          <span className="why" id="why-claude-brief">이번 달 상한 도달</span>
          <button className="btn btn-primary needs-claude" aria-describedby="why-claude-brief" onClick={run} disabled={busy || (!text.trim() && !file) || level === 'over'}>
            {busy ? '요약하는 중…' : '✳ 사장님 말투로 요약'}
          </button>
        </div>
        {err && <p role="alert" className="error">{err}</p>}
      </section>

      {summary && (
        <>
          <section className="card">
            <label className="block">
              요약문(고쳐서 쓸 수 있어요)
              <textarea className="field" rows={5} value={summary} onChange={(e) => setSummary(e.target.value)} />
            </label>
          </section>
          <SpeechMaker text={summary} kind="briefing" title={`브리핑 ${new Date().toLocaleDateString('ko-KR')}`} />
        </>
      )}
    </>
  )
}
