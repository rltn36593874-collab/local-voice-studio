import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api.js'
import { fmtSec } from '../lib/rules.js'
import { JOB_LABEL, isActive, useShell } from '../lib/shell.js'

/** 1초마다 작업 상태를 읽는다. 끝나면(done) onDone(job)을 한 번 부른다 */
export function useJob(jobId, onDone) {
  const [job, setJob] = useState(null)
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  useEffect(() => {
    setJob(null)
    if (!jobId) return
    let stop = false
    let timer
    const poll = async () => {
      try {
        const j = await api.getJob(jobId)
        if (stop) return
        setJob(j)
        if (!isActive(j.status)) {
          if (j.status === 'done') doneRef.current?.(j)
          return
        }
      } catch (e) {
        if (stop) return
        // 서버가 잠깐 바쁠 수 있으니 상태는 그대로 두고 다시 묻는다
        setJob((j) => j && { ...j, pollError: e.message })
      }
      timer = setTimeout(poll, 1000)
    }
    poll()
    return () => {
      stop = true
      clearTimeout(timer)
    }
  }, [jobId])
  return job
}

export function ProgressBar({ value }) {
  const indeterminate = value == null
  return (
    <div
      className={`progress${indeterminate ? ' indet' : ''}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(value * 100)}
    >
      <i style={indeterminate ? undefined : { '--p': `${value * 100}%` }} />
    </div>
  )
}

/** 화면 안 작업 카드(디자인 02 §2-2 ①). progress=null이면 줄무늬 바 + 경과 시간만 */
export default function JobCard({ jobId, onDone, onRetry }) {
  const job = useJob(jobId, onDone)
  const { pokeJobs } = useShell()
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  if (!job) return null

  const active = isActive(job.status)
  const elapsed = job.created_at ? (now - Date.parse(job.created_at)) / 1000 : 0
  const barValue = job.status === 'queued' ? 0 : job.status === 'running' ? job.progress : null

  return (
    <div className={`job-card ${job.status}`}>
      <div className="top" aria-live="polite">
        <strong>{job.cancel_requested && active ? '취소 중' : JOB_LABEL[job.status]}</strong>
        <span className="step">
          {job.status === 'queued' && `앞에 ${job.queue_position}개 작업이 있어요`}
          {job.status === 'preparing' && '모델 불러오는 중'}
        </span>
        <span className="spacer" />
        {job.status === 'running' && job.progress != null && <span className="mono">{Math.round(job.progress * 100)}%</span>}
        {active && !job.cancel_requested && (
          <button className="btn btn-ghost btn-sm" onClick={() => api.cancelJob(job.id).then(pokeJobs)}>
            취소
          </button>
        )}
      </div>
      {active && <ProgressBar value={barValue} />}
      {active && (
        <div className="meta">
          <span>경과 <span className="mono">{fmtSec(elapsed)}</span></span>
          {job.eta_sec != null && <span>남은 시간 약 <span className="mono">{fmtSec(job.eta_sec)}</span></span>}
        </div>
      )}
      {job.pollError && <p className="muted">서버 응답을 기다리는 중… ({job.pollError})</p>}
      {job.status === 'failed' && (
        <p role="alert" className="error">
          {job.error?.message ?? '처리하지 못했어요'}{' '}
          {onRetry && <button className="btn" onClick={onRetry}>다시 시도</button>}
        </p>
      )}
    </div>
  )
}
