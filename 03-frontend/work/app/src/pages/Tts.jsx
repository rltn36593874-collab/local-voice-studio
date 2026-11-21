import { useState } from 'react'
import { api } from '../lib/api.js'
import { useShell } from '../lib/shell.js'
import SpeechMaker from '../components/SpeechMaker.jsx'

/** ① 음성 만들기: 대본 → (Claude로 다듬기) → 로컬 TTS */
export default function Tts() {
  const { level, refreshUsage } = useShell()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')

  async function refine() {
    setBusy(true)
    setErr('')
    try {
      const r = await api.refineScript({ text })
      setText(r.text)
      setNote(`Claude 사용: 입력 ${r.usage.input_tokens} · 출력 ${r.usage.output_tokens} 토큰`)
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
          대본
          <textarea className="field" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder="읽을 대본을 입력하세요. 숫자·영문·상호는 'Claude로 다듬기'가 한글 읽기로 바꿔 줘요." />
        </label>
        <div className="row">
          <span className="muted">{text.length.toLocaleString()}자 / 5,000자</span>
          <span className="spacer" />
          {note && <span className="muted">{note}</span>}
          <span className="why" id="why-claude-tts">이번 달 상한 도달</span>
          <button className="btn needs-claude" aria-describedby="why-claude-tts" onClick={refine} disabled={busy || !text.trim() || level === 'over'}>
            {busy ? '다듬는 중…' : '✳ Claude로 대본 다듬기'}
          </button>
        </div>
        {err && <p role="alert" className="error">{err}</p>}
      </section>
      <SpeechMaker text={text} kind="tts" />
    </>
  )
}
