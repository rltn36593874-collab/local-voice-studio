import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { checkTotal, dateAfter } from '../lib/rules.js'
import { useShell } from '../lib/shell.js'
import Recorder from '../components/Recorder.jsx'
import SampleList, { totalSec } from '../components/SampleList.jsx'
import JobCard from '../components/JobCard.jsx'

const STEPS = ['주인 확인', '동의 낭독', '목소리 샘플', '이름·저장']
// 보관 규칙(대표 결정 11-22, 디자인 02 ④)
const RETENTION = '동의 기록은 목소리가 있는 동안 보관하고, 목소리를 지우면 365일 뒤 삭제해요. 복제 샘플은 목소리를 지울 때 함께 지워져요.'

/** ④ 목소리 복제: 기획 §3 — 주인 확인 → 동의 낭독 → 샘플 → 이름·저장 → 내 목소리 목록·삭제 */
export default function Clone() {
  const { pokeJobs } = useShell()
  const [owner, setOwner] = useState('self')
  const [subject, setSubject] = useState('')
  const [doc, setDoc] = useState(null)
  const [sent, setSent] = useState(null) // {sentence, nonce, expires_at}
  const [consentId, setConsentId] = useState(null)
  const [samples, setSamples] = useState([])
  const [name, setName] = useState('')
  const [jobId, setJobId] = useState(null)
  const [voices, setVoices] = useState([])
  const [oldConsents, setOldConsents] = useState([])
  const [notice, setNotice] = useState('')
  const [err, setErr] = useState('')

  const loadVoices = () => {
    api.listVoices().then((v) => setVoices(v.filter((x) => x.kind === 'clone')), (e) => setErr(e.message))
    api.listConsents().then(setOldConsents, () => {})
  }
  useEffect(() => void loadVoices(), [])

  const ownerReady = owner === 'self' || (subject.trim() && doc)

  async function getSentence() {
    setErr('')
    setConsentId(null)
    try {
      setSent(await api.consentSentence())
    } catch (e) {
      setErr(e.message)
    }
  }

  async function saveConsent(audio) {
    setErr('')
    try {
      const other = owner === 'other'
      const r = await api.saveConsent({ owner, nonce: sent.nonce, audio, consent_doc: other ? doc : null, subject_name: other ? subject : null })
      setConsentId(r.consent_id)
    } catch (e) {
      setErr(e.message)
      if (e.code === 'nonce_expired') setSent(null)
    }
  }

  const usable = samples.filter((s) => !s.error)
  const samplesOk = usable.length > 0 && !checkTotal(totalSec(samples))
  const canSubmit = consentId && name.trim() && samplesOk && !jobId
  const step = !consentId ? (sent ? 1 : 0) : samplesOk ? 3 : 2

  async function submit() {
    setErr('')
    try {
      const { job_id } = await api.cloneVoice({ name, consent_id: consentId, files: usable.map((s) => s.file) })
      setJobId(job_id)
      pokeJobs()
    } catch (e) {
      setErr(e.message)
    }
  }

  function onCloned() {
    loadVoices()
    setNotice(`'${name}' 목소리가 준비됐어요. ① 음성 만들기에서 고를 수 있어요.`)
    // 동의 하나로 목소리 하나(백엔드 consent_used). 다음 복제는 처음부터.
    samples.forEach((s) => URL.revokeObjectURL(s.url))
    setSamples([])
    setSent(null)
    setConsentId(null)
    setName('')
  }

  async function remove(v) {
    if (!confirm(`'${v.name}' 목소리를 삭제할까요?
복제 샘플은 바로 지워지고, 동의 기록은 ${dateAfter(365)}에 삭제될 예정이에요.`)) return
    try {
      await api.deleteVoice(v.id)
      loadVoices()
    } catch (e) {
      setErr(e.message)
    }
  }

  return (
    <>
      <ol className="stepper" aria-label="진행 단계">
        {STEPS.map((s, i) => (
          <li key={s} className={i < step ? 'done' : i === step ? 'now' : ''} aria-current={i === step ? 'step' : undefined}>{s}</li>
        ))}
      </ol>
        <section className="card">
          <h3>1. 이 목소리의 주인</h3>
          <div className="seg" role="group" aria-label="목소리 주인">
            {[['self', '본인(대표)'], ['other', '다른 사람']].map(([v, l]) => (
              <button key={v} aria-pressed={owner === v} onClick={() => (setOwner(v), setConsentId(null))} disabled={!!consentId}>
                {l}
              </button>
            ))}
          </div>
          {owner === 'other' && (
            <div className="row wrap">
              <label>이름 <input className="field" value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
              <label>동의서(pdf·jpg·png) <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setDoc(e.target.files[0] ?? null)} /></label>
            </div>
          )}
        </section>

        <section className="card">
          <h3>2. 동의 낭독</h3>
          {!ownerReady && <p className="muted">다른 사람의 목소리는 이름과 동의서를 먼저 올려 주세요.</p>}
          <p className="faint">{RETENTION}</p>
          {consentId ? (
            <p>✓ 동의 기록을 저장했어요.</p>
          ) : sent ? (
            <>
              <blockquote className="consent">{sent.sentence}</blockquote>
              <p className="muted">
                위 문장을 소리 내어 읽고 정지를 누르세요. {new Date(sent.expires_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}까지 유효해요.
              </p>
              <Recorder maxSec={30} startLabel="낭독 녹음" onDone={saveConsent} />
            </>
          ) : (
            <button className="btn" onClick={getSentence} disabled={!ownerReady}>동의 문장 받기</button>
          )}
        </section>

        <section className="card">
          <h3>3. 목소리 샘플</h3>
          <fieldset disabled={!consentId}>
            <SampleList samples={samples} setSamples={setSamples} disabled={!consentId} />
          </fieldset>
        </section>

        <section className="card">
          <h3>4. 이름 붙이고 저장</h3>
          <div className="row wrap">
            <label>이름 <input className="field" value={name} onChange={(e) => setName(e.target.value)} disabled={!consentId} /></label>
            <span className="spacer" />
            <span className="muted">로컬 처리 · 시간이 걸릴 수 있어요</span>
            <button className="btn btn-primary" onClick={submit} disabled={!canSubmit}>목소리 만들기</button>
          </div>
          {jobId && <JobCard key={jobId} jobId={jobId} onDone={onCloned} />}
          {notice && <p role="status">{notice}</p>}
        </section>

      {err && <p role="alert" className="error">{err}</p>}

      <section className="card">
        <h3>내 목소리</h3>
        {voices.length === 0 ? (
          <p className="muted">아직 만든 목소리가 없어요.</p>
        ) : (
          <ul className="voice-list">
            {voices.map((v) => (
              <li key={v.id} className="voice-item">
                <span>{v.name}</span>
                <span className="muted">{new Date(v.created_at).toLocaleDateString('ko-KR')}</span>
                <span className="spacer" />
                <button className="btn btn-danger btn-sm" onClick={() => remove(v)}>삭제</button>
              </li>
            ))}
          </ul>
        )}
        {oldConsents.length > 0 && (
          <ul className="voice-list">
            {oldConsents.map((c) => (
              <li key={c.id} className="voice-item">
                <span className="muted">{c.voice_name} · 동의 기록</span>
                <span className="spacer" />
                <span className="faint">{c.purge_at.slice(0, 10)} 삭제 예정</span>
              </li>
            ))}
          </ul>
        )}
        <p className="faint">{RETENTION}</p>
      </section>
    </>
  )
}
