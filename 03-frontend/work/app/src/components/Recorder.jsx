import { useEffect, useRef, useState } from 'react'
import { fmtSec, pickMimeType } from '../lib/rules.js'

// 녹음 패널(rec-panel). 상태 이름은 디자인 1단계 3-6절:
// S0 대기 → S1 권한 요청 → S2 녹음 중 → (정지/maxSec) onDone → S0, 실패는 S1x 권한 거부
const LOUD = 0.98 // 피크가 이보다 크면 "소리가 너무 커요"
const QUIET = 0.02 // 이보다 작은 상태가 5초 넘으면 "소리가 안 들려요"

export default function Recorder({ maxSec = 180, onDone, startLabel = '마이크로 녹음', disabled }) {
  const [state, setState] = useState('S0')
  const [err, setErr] = useState('')
  const [sec, setSec] = useState(0)
  const [level, setLevel] = useState(0)
  const [warn, setWarn] = useState('')
  const live = useRef(null)

  // 녹음 중 탭 닫기·새로고침 경고(녹음본 손실 방지)
  useEffect(() => {
    if (state !== 'S2') return
    const f = (e) => e.preventDefault()
    addEventListener('beforeunload', f)
    return () => removeEventListener('beforeunload', f)
  }, [state])

  // 컴포넌트가 사라지면 마이크를 놓는다
  useEffect(() => () => stop(true), [])

  async function begin() {
    setErr('')
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setErr('보안 연결(https 또는 이 PC 주소)에서만 녹음할 수 있어요')
      return setState('S1x')
    }
    // 이미 허용돼 있으면 안내 카드 없이 바로 시작
    const perm = await navigator.permissions?.query({ name: 'microphone' }).then((p) => p.state).catch(() => 'prompt')
    if (perm === 'granted') return record()
    setState('S1')
  }

  async function record() {
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    } catch (e) {
      setErr(
        e.name === 'NotFoundError'
          ? '연결된 마이크를 찾지 못했어요'
          : '마이크 사용이 막혀 있어요. 주소창 왼쪽 자물쇠 → 마이크 → 허용 후 다시 시도하세요',
      )
      return setState('S1x')
    }
    const mimeType = pickMimeType((t) => MediaRecorder.isTypeSupported(t))
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks = []
    const ctx = new AudioContext()
    const analyser = ctx.createAnalyser()
    ctx.createMediaStreamSource(stream).connect(analyser)
    const buf = new Uint8Array(analyser.fftSize)
    const t0 = performance.now()
    let lastSound = t0

    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      ctx.close()
      const s = (performance.now() - t0) / 1000
      setState('S0')
      setLevel(0)
      setWarn('')
      if (live.current?.discard) return
      const ext = rec.mimeType.includes('mp4') ? 'm4a' : rec.mimeType.includes('ogg') ? 'ogg' : 'webm'
      const file = new File(chunks, `녹음-${new Date().toTimeString().slice(0, 8).replaceAll(':', '')}.${ext}`, { type: rec.mimeType })
      onDone(file, s)
    }

    const tick = () => {
      analyser.getByteTimeDomainData(buf)
      let peak = 0
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128) / 128)
      const t = performance.now()
      const s = (t - t0) / 1000
      if (peak > QUIET) lastSound = t
      setLevel(peak)
      setSec(s)
      setWarn(
        peak > LOUD ? '소리가 너무 커요. 마이크에서 조금 떨어져 주세요'
        : t - lastSound > 5000 ? '소리가 안 들려요. 마이크를 확인해 주세요'
        : maxSec - s <= 15 ? `${Math.ceil(maxSec - s)}초 뒤 자동으로 멈춰요`
        : '',
      )
      if (s >= maxSec) return stop(false)
      live.current.raf = requestAnimationFrame(tick)
    }

    live.current = { rec, discard: false, raf: requestAnimationFrame(tick) }
    rec.start(1000)
    setSec(0)
    setState('S2')
  }

  function stop(discard) {
    const l = live.current
    if (!l) return
    l.discard = discard
    cancelAnimationFrame(l.raf)
    if (l.rec.state !== 'inactive') l.rec.stop()
    live.current = null
  }

  return (
    <div className={state === 'S0' ? 'rec-idle' : `rec-panel rec-${state}`}>
      {state === 'S0' && (
        <button className="btn" onClick={begin} disabled={disabled}>
          ● {startLabel}
        </button>
      )}

      {state === 'S1' && (
        <div className="rec-body">
          <p>목소리를 녹음하려면 마이크가 필요해요. 녹음은 정지를 누를 때까지만 진행돼요.</p>
          <p className="muted">버튼을 누른 뒤 브라우저 창에서 '허용'을 눌러 주세요.</p>
          <div className="row">
            <button className="btn btn-primary" onClick={record}>마이크 허용하기</button>
            <button className="btn btn-ghost" onClick={() => setState('S0')}>취소</button>
          </div>
        </div>
      )}

      {state === 'S1x' && (
        <div className="rec-body">
          <p role="alert" className="error">{err}</p>
          <div className="row">
            <button className="btn btn-ghost" onClick={begin}>다시 시도</button>
            <span className="muted">또는 위에서 파일을 올려 주세요</span>
          </div>
        </div>
      )}

      {state === 'S2' && (
        <div className="rec-body">
          <div className="row">
            <span className="rec-dot" aria-hidden="true" />
            <strong>녹음 중</strong>
            <span className="rec-time mono" aria-live="polite" aria-atomic="true">
              {fmtSec(sec)} / {fmtSec(maxSec)}
            </span>
            <span className="spacer" />
            <button className="btn btn-primary btn-lg" onClick={() => stop(false)} autoFocus>■ 정지</button>
            <button className="btn btn-ghost" onClick={() => stop(true)}>버리기</button>
          </div>
          <meter className="level-meter" min={0} max={1} low={0.05} high={0.9} optimum={0.5} value={level} aria-label="입력 레벨" />
          <p role="status">{warn && <span className="badge badge-warn">{warn}</span>}</p>
        </div>
      )}
    </div>
  )
}
