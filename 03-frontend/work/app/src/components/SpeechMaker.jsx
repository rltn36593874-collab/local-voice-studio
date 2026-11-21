import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import JobCard from './JobCard.jsx'
import ResultCard from './ResultCard.jsx'
import { useShell } from '../lib/shell.js'

/** 음성 선택·속도·형식 → TTS 작업 → 진행 → 결과. ① 음성 만들기와 ③ 보고서 브리핑이 같이 쓴다 */
export default function SpeechMaker({ text, kind = 'tts', title }) {
  const { pokeJobs } = useShell()
  const [voices, setVoices] = useState([])
  const [voiceId, setVoiceId] = useState('')
  const [speed, setSpeed] = useState(1)
  const [format, setFormat] = useState('mp3')
  const [jobId, setJobId] = useState(null)
  const [output, setOutput] = useState(null)
  const [err, setErr] = useState('')

  const loadVoices = () =>
    api.listVoices().then((v) => {
      setVoices(v)
      setVoiceId((cur) => (v.some((x) => x.id === cur) ? cur : v[0]?.id ?? ''))
    }, (e) => setErr(e.message))
  useEffect(() => void loadVoices(), [])

  async function generate() {
    setErr('')
    setOutput(null)
    try {
      const { job_id } = await api.createTts({ text, voice_id: voiceId, speed, format, title, kind })
      setJobId(job_id)
      pokeJobs()
    } catch (e) {
      setErr(e.message)
    }
  }

  async function onDone(job) {
    const list = await api.listOutputs()
    setOutput(list.find((o) => o.id === job.result?.output_id) ?? null)
  }

  return (
    <section className="card">
      <div className="row wrap">
        <label>
          음성
          {/* 복제 화면에서 새 목소리를 만들었을 수 있으니 열 때마다 다시 읽는다 */}
          <select className="field" value={voiceId} onChange={(e) => setVoiceId(e.target.value)} onFocus={loadVoices}>
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.kind === 'clone' ? `내 목소리 · ${v.name}` : v.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          속도 {speed.toFixed(1)}×
          <input type="range" min={0.7} max={1.3} step={0.1} value={speed} onChange={(e) => setSpeed(+e.target.value)} />
        </label>
        <div className="seg" role="group" aria-label="저장 형식">
          {['mp3', 'wav'].map((f) => (
            <button key={f} aria-pressed={format === f} onClick={() => setFormat(f)}>
              {f.toUpperCase()}
            </button>
          ))}
        </div>
        <span className="spacer" />
        <span className="muted">로컬 처리 · 비용 없음</span>
        <button className="btn btn-primary" onClick={generate} disabled={!text?.trim() || !voiceId}>
          음성 만들기
        </button>
      </div>
      {err && <p role="alert" className="error">{err}</p>}
      {jobId && <JobCard key={jobId} jobId={jobId} onDone={onDone} onRetry={generate} />}
      {output && <ResultCard output={output} />}
    </section>
  )
}
