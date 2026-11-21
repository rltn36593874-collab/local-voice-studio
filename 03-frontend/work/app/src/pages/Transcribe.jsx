import { useState } from 'react'
import { api } from '../lib/api.js'
import { fmtSec } from '../lib/rules.js'
import { useShell } from '../lib/shell.js'
import JobCard from '../components/JobCard.jsx'

// 백엔드 지원 언어(04-backend §3.5)
const LANGS = [['en', '영어'], ['ja', '일본어'], ['zh', '중국어'], ['vi', '베트남어'], ['es', '스페인어'], ['fr', '프랑스어'], ['de', '독일어']]

/** ② 받아쓰기: 파일 → 로컬 전사(작업) → 전사문 → 요약·SRT·번역 */
export default function Transcribe() {
  const { level, refreshUsage, pokeJobs } = useShell()
  const [file, setFile] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [tr, setTr] = useState(null)
  const [summary, setSummary] = useState(null)
  const [lang, setLang] = useState('en')
  const [trJobId, setTrJobId] = useState(null)
  const [links, setLinks] = useState({}) // lang → {srt, txt}
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const fail = (e) => setErr(e.message)

  async function start() {
    setErr('')
    setTr(null)
    setSummary(null)
    setLinks({})
    try {
      setJobId((await api.transcribe(file)).job_id)
      pokeJobs()
    } catch (e) {
      fail(e)
    }
  }

  async function addLinks(id, l) {
    const [srt, txt] = await Promise.all([api.srtUrl(id, l), api.txtUrl(id, l)])
    setLinks((x) => ({ ...x, [l]: { srt, txt } }))
  }

  async function onTranscribed(job) {
    const t = await api.getTranscript(job.result.transcript_id)
    setTr(t)
    addLinks(t.id, 'ko')
  }

  async function summarize() {
    setBusy(true)
    try {
      setSummary(await api.summarizeTranscript(tr.id))
      refreshUsage()
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  async function translate() {
    try {
      setTrJobId((await api.translateTranscript(tr.id, lang)).job_id)
      pokeJobs()
      refreshUsage()
    } catch (e) {
      fail(e)
    }
  }

  const claudeOff = level === 'over'

  return (
    <>
      <section className="card">
        <div className="row wrap">
          <label>
            녹음·영상 파일 <input type="file" accept="audio/*,video/*" onChange={(e) => setFile(e.target.files[0] ?? null)} />
          </label>
          <span className="spacer" />
          <span className="muted">로컬 처리 · 긴 파일은 걸어 두고 다른 일을 하셔도 돼요</span>
          <button className="btn btn-primary" onClick={start} disabled={!file}>받아쓰기 시작</button>
        </div>
        <p className="faint">올린 원본 파일은 30일 보관 후 자동으로 지워져요. 전사문과 자막은 기록에 남아요.</p>
        {err && <p role="alert" className="error">{err}</p>}
        {jobId && <JobCard key={jobId} jobId={jobId} onDone={onTranscribed} onRetry={start} />}
      </section>

      {tr && (
        <section className="card">
          <div className="row wrap">
            <strong>{tr.source_name}</strong>
            <span className="muted">{fmtSec(tr.duration_sec)}</span>
            {tr.source_expires_at && <span className="faint">원본 {tr.source_expires_at.slice(0, 10)} 삭제 예정</span>}
            <span className="spacer" />
            <a className="btn btn-ghost" href={links.ko?.srt} download={`${tr.source_name}.ko.srt`}>SRT</a>
            <a className="btn btn-ghost" href={links.ko?.txt} download={`${tr.source_name}.ko.txt`}>TXT</a>
            <span className="why" id="why-claude-sum">이번 달 상한 도달</span>
            <button className="btn needs-claude" aria-describedby="why-claude-sum" onClick={summarize} disabled={busy || claudeOff}>{busy ? '요약하는 중…' : '✳ 요약·회의록'}</button>
          </div>
          <div className="transcript">
            {tr.segments.map((s, i) => (
              <div key={i} className="seg-line">
                <time className="ts mono">{fmtSec(s.start)}</time><span>{s.text}</span>
              </div>
            ))}
          </div>

          {summary && (
            <div className="card">
              <p>{summary.summary}</p>
              {summary.decisions.length > 0 && <p><strong>결정</strong> {summary.decisions.join(' · ')}</p>}
              {summary.todos.length > 0 && <p><strong>할 일</strong> {summary.todos.join(' · ')}</p>}
            </div>
          )}

          <div className="row wrap">
            <label>
              자막 번역
              <select className="field" value={lang} onChange={(e) => setLang(e.target.value)}>
                {LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <span className="why" id="why-claude-tr">이번 달 상한 도달</span>
            <button className="btn needs-claude" aria-describedby="why-claude-tr" onClick={translate} disabled={claudeOff}>✳ 번역</button>
            {Object.entries(links)
              .filter(([l]) => l !== 'ko')
              .map(([l, u]) => (
                <a key={l} className="btn btn-ghost" href={u.srt} download={`${tr.source_name}.${l}.srt`}>{l} SRT</a>
              ))}
          </div>
          {trJobId && <JobCard key={trJobId} jobId={trJobId} onDone={(j) => addLinks(tr.id, j.result.lang)} onRetry={translate} />}
        </section>
      )}
    </>
  )
}
