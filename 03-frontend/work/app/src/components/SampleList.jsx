import { useState } from 'react'
import Recorder from './Recorder.jsx'
import { ProgressBar } from './JobCard.jsx'
import { LIMITS, checkFile, checkTotal, fmtSec } from '../lib/rules.js'

/** 실제로 디코딩한 길이(초). 못 열면 NaN */
export async function durationOf(blob) {
  const ctx = new AudioContext()
  try {
    return (await ctx.decodeAudioData(await blob.arrayBuffer())).duration
  } catch {
    return NaN
  } finally {
    ctx.close()
  }
}

export const totalSec = (samples) => samples.filter((s) => !s.error).reduce((a, s) => a + s.sec, 0)

/**
 * 복제 샘플: 드롭존(파일) + 녹음 + 샘플 목록 + 합계 진행 막대.
 * 디자인 1단계 3-6: S3 길이 미달·초과 배너, S4 검토 목록, S5 파일 오류 행.
 * shortcut: 진행 링·정적 파형은 막대·<audio>로 대신함, 디자인 시안(rec-panel·dropzone) 오면 교체.
 */
export default function SampleList({ samples, setSamples, disabled }) {
  const [over, setOver] = useState(false)

  async function add(files, wallSec) {
    const items = await Promise.all(
      [...files].map(async (file) => {
        let sec = await durationOf(file)
        if (Number.isNaN(sec) && wallSec) sec = wallSec // 녹음본 디코딩 실패 시 녹음 시간으로
        return { id: crypto.randomUUID(), file, sec, url: URL.createObjectURL(file), error: checkFile({ size: file.size, durationSec: sec }) }
      }),
    )
    setSamples((s) => [...s, ...items])
  }

  function remove(id) {
    setSamples((s) => {
      const gone = s.find((x) => x.id === id)
      if (gone) URL.revokeObjectURL(gone.url)
      return s.filter((x) => x.id !== id)
    })
  }

  const total = totalSec(samples)
  const totalErr = samples.length ? checkTotal(total) : null

  return (
    <div className="samples">
      <label
        className={`dropzone${over ? ' dropzone-over' : ''}`}
        onDragOver={(e) => (e.preventDefault(), setOver(true))}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          if (!disabled) add(e.dataTransfer.files)
        }}
      >
        <input type="file" accept="audio/*" multiple hidden disabled={disabled} onChange={(e) => (add(e.target.files), (e.target.value = ''))} />
        <strong>파일을 끌어다 놓거나 눌러서 고르세요</strong>
        <span className="muted">파일당 10MB · 5초 이상 · 합계 10초~3분 · 조용한 곳에서 1~2분이면 충분해요</span>
      </label>

      <Recorder maxSec={LIMITS.maxTotalSec} onDone={(file, s) => add([file], s)} disabled={disabled} />

      {samples.length > 0 && (
        <ul className="sample-rows">
          {samples.map((s) => (
            <li key={s.id} className={`sample${s.error ? ' sample-error' : ''}`}>
              <span className="ellipsis">{s.file.name}</span>
              <span className="muted">{Number.isNaN(s.sec) ? '—' : fmtSec(s.sec)}</span>
              {!s.error && <audio controls preload="metadata" src={s.url} />}
              {s.error && <span role="alert" className="error">{s.error.message}</span>}
              <button className="btn btn-ghost" onClick={() => remove(s.id)} aria-label={`${s.file.name} 삭제`}>삭제</button>
            </li>
          ))}
        </ul>
      )}

      <div className="total">
        <div className="row">
          <span>합계 {fmtSec(total)} / 3:00</span>
          <span className="muted">최소 0:10 · 권장 1:00~2:00</span>
        </div>
        <div className={`total-bar${samples.length && total < LIMITS.minTotalSec ? ' total-short' : ''}`}>
          <ProgressBar value={Math.min(1, total / LIMITS.maxTotalSec)} />
          <b style={{ left: `${(LIMITS.minTotalSec / LIMITS.maxTotalSec) * 100}%` }} title="최소 0:10" aria-hidden="true" />
        </div>
        {totalErr && (
          <p className={totalErr.code === 'too_long' ? 'error' : 'warn'} role="status">
            {totalErr.message}
          </p>
        )}
      </div>
    </div>
  )
}
