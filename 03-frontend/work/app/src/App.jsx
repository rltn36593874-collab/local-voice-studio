import { useCallback, useEffect, useRef, useState } from 'react'
import { api, IS_MOCK } from './lib/api.js'
import { usageLevel } from './lib/rules.js'
import { ShellContext, JOB_LABEL, JOB_TYPE, isActive } from './lib/shell.js'
import { ProgressBar } from './components/JobCard.jsx'
import Tts from './pages/Tts.jsx'
import Transcribe from './pages/Transcribe.jsx'
import Briefing from './pages/Briefing.jsx'
import Clone from './pages/Clone.jsx'
import History from './pages/History.jsx'

// 5화면(기획 §5). 라우팅은 해시(#/tts)로 충분하다(로컬 1인 도구, 서버 라우팅 불필요).
const ROUTES = [
  { path: '/tts', label: '① 음성 만들기', desc: '대본을 다듬고 로컬 음성으로 읽어요', Page: Tts, types: ['tts'] },
  { path: '/transcribe', label: '② 받아쓰기', desc: '녹음을 글로 옮기고 요약·자막을 만들어요', Page: Transcribe, types: ['transcribe', 'translate'] },
  { path: '/briefing', label: '③ 보고서 브리핑', desc: '보고서를 쉬운 말로 줄여 음성으로 들려줘요', Page: Briefing, types: [] },
  { path: '/clone', label: '④ 목소리 복제', desc: '동의를 받은 목소리만 복제해요', Page: Clone, types: ['clone'] },
  { path: '/history', label: '⑤ 기록', desc: '만든 결과와 이번 달 Claude 사용량', Page: History, types: [] },
]
const RESULT_ROUTE = { tts: '/history', transcribe: '/transcribe', translate: '/transcribe', clone: '/clone' }
const hashPath = () => (ROUTES.some((r) => `#${r.path}` === location.hash) ? location.hash.slice(1) : '/tts')
const today = () => new Date().toISOString().slice(0, 10)

function bannerDismissedToday() {
  try {
    return localStorage.getItem('usageBannerOff') === today()
  } catch {
    return false
  }
}

function healthText(h) {
  if (!h) return '확인 중…'
  if (!h.ok) return '로컬 서버에 연결되지 않았어요'
  const idle = Object.entries(h.engines ?? {}).filter(([, e]) => !e.loaded).map(([k]) => k.toUpperCase())
  const parts = [idle.length ? `${idle.join('·')} 대기 중 · 첫 작업이 느려요` : '모델 준비됨']
  if (!h.claude_key_present) parts.push('Claude 키 없음')
  return parts.join(' · ')
}

export default function App() {
  const [path, setPath] = useState(hashPath)
  const [usage, setUsage] = useState(null)
  const [jobs, setJobs] = useState({ active: [], recent: [] })
  const [health, setHealth] = useState(null)
  const [drawer, setDrawer] = useState(false)
  const [toast, setToast] = useState(null)
  const [bannerOff, setBannerOff] = useState(bannerDismissedToday)
  const [poke, setPoke] = useState(0)
  const seen = useRef(null) // 이미 알린 끝난 작업 id(첫 로드 때는 알리지 않음)

  useEffect(() => {
    const f = () => setPath(hashPath())
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])

  const refreshUsage = useCallback(() => api.getUsage().then(setUsage, () => {}), [])
  const pokeJobs = useCallback(() => setPoke((n) => n + 1), [])
  useEffect(() => void refreshUsage(), [refreshUsage])

  useEffect(() => {
    const f = () => api.getHealth().then(setHealth, () => setHealth({ ok: false }))
    f()
    const t = setInterval(f, 10000)
    return () => clearInterval(t)
  }, [])

  // 작업 목록 1초 폴링(상단 표시기·서랍·완료 토스트). pokeJobs()로 즉시 다시 읽는다.
  useEffect(() => {
    let stop = false
    let t
    const f = async () => {
      try {
        const j = await api.listJobs()
        if (stop) return
        setJobs(j)
        if (seen.current) {
          const fresh = j.recent.find((x) => !seen.current.has(x.id) && x.status === 'done')
          if (fresh) setToast(fresh)
        }
        seen.current = new Set([...(seen.current ?? []), ...j.recent.map((x) => x.id)])
      } catch {
        // 서버가 꺼져 있으면 nav-foot의 health가 알린다
      }
      if (!stop) t = setTimeout(f, 1000)
    }
    f()
    return () => {
      stop = true
      clearTimeout(t)
    }
  }, [poke])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 6000)
    return () => clearTimeout(t)
  }, [toast])

  const level = usageLevel(usage)
  useEffect(() => {
    document.body.dataset.usage = level // 시안 CSS가 body[data-usage]로 경고색을 바꾼다
  }, [level])

  useEffect(() => {
    const f = (e) => e.key === 'Escape' && setDrawer(false)
    addEventListener('keydown', f)
    return () => removeEventListener('keydown', f)
  }, [])

  function dismissBanner() {
    try {
      localStorage.setItem('usageBannerOff', today())
    } catch {}
    setBannerOff(true)
  }

  const route = ROUTES.find((r) => r.path === path)
  const running = jobs.active.filter((j) => j.status !== 'queued').length
  const waiting = jobs.active.length - running
  const pct = usage ? Math.min(100, Math.round((usage.est_usd / (usage.limit_usd || 1)) * 100)) : 0

  return (
    <ShellContext.Provider value={{ usage, level, refreshUsage, pokeJobs }}>
      <div className="app-shell">
        <nav className="nav" aria-label="메뉴">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">◐</span>사내 음성
          </div>
          {ROUTES.map((r) => (
            <a key={r.path} href={`#${r.path}`} aria-current={r.path === path ? 'page' : undefined}>
              {r.label}
              {jobs.active.some((j) => r.types.includes(j.type)) && <span className="dot" title="진행 중인 작업" />}
            </a>
          ))}
          <div className="nav-foot" role="status">
            {health?.ok && <span className="ok" aria-hidden="true" />} {healthText(health)}
          </div>
        </nav>

        <header className="topbar">
          <h1>{route.label}</h1>
          {IS_MOCK && <span className="badge badge-warn" title="백엔드 연결 전 가짜 데이터">mock</span>}
          <span className="spacer" />
          <button className="jobs-btn" onClick={() => setDrawer(true)} aria-expanded={drawer} aria-controls="job-drawer">
            {running > 0 && <span className="pulse" aria-hidden="true" />}
            {jobs.active.length ? `작업 ${running} · 대기 ${waiting}` : <span className="faint">작업 없음</span>}
          </button>
          <a className="usage-meter" href="#/history" title="이번 달 Claude 사용량">
            {/* none(상한 미입력)이면 금액만, 상한이 있으면 %와 막대 */}
            ✳ Claude <b className="mono">{level === 'none' ? `$${(usage?.est_usd ?? 0).toFixed(2)}` : `${pct}%`}</b>
            <span className="bar" aria-hidden="true" hidden={level === 'none'}>
              <i style={{ '--pct': `${pct}%` }} />
            </span>
          </a>
        </header>

        <main className="main">
          {!bannerOff && (
            <div className="banner b-warn" role="status">
              Claude 사용량이 한도의 80%를 넘었어요. <span>로컬 기능은 그대로 쓸 수 있어요.</span>
              <span className="spacer" />
              <button className="btn btn-ghost btn-sm" onClick={dismissBanner}>오늘 그만 보기</button>
            </div>
          )}
          <div className="banner b-over" role="alert">
            이번 달 Claude 한도에 닿았어요. <span>✳ 기능은 잠기고 로컬 기능은 계속 쓸 수 있어요.</span>
          </div>
          <div className="content">
            <div className="screen-head">
              <div>
                <h2>{route.label}</h2>
                <p>{route.desc}</p>
              </div>
            </div>
            {/* 모든 화면을 살려 두고 숨긴다: 화면을 옮겨도 녹음·작업 진행·입력이 사라지지 않게 */}
            {ROUTES.map(({ path: p, Page }) => (
              <div key={p} hidden={p !== path}>
                <Page active={p === path} />
              </div>
            ))}
          </div>
        </main>
      </div>

      <aside id="job-drawer" className="drawer" data-open={drawer} aria-label="작업 패널" inert={!drawer}>
        <header>
          <h3>작업</h3>
          <span className="spacer" />
          <button className="icon-btn" onClick={() => setDrawer(false)} aria-label="닫기">✕</button>
        </header>
        <div className="body">
          <div className="group">
            <span className="label">진행 중 · 대기</span>
            {jobs.active.length === 0 && <p className="muted">처리 중인 작업이 없어요.</p>}
            {jobs.active.map((j, i) => (
              <div key={j.id} className="q-item">
                <span className="n">{i + 1}</span>
                <span className="spacer ellipsis">
                  {JOB_TYPE[j.type]} · {j.title}
                  <br />
                  <span className="faint">{j.cancel_requested ? '취소 중' : JOB_LABEL[j.status]}</span>
                </span>
                {!j.cancel_requested && (
                  <button className="btn btn-ghost btn-sm" onClick={() => api.cancelJob(j.id).then(pokeJobs)}>취소</button>
                )}
              </div>
            ))}
            {jobs.active[0]?.status === 'running' && <ProgressBar value={jobs.active[0].progress} />}
          </div>
          <div className="group">
            <span className="label">최근 끝난 작업</span>
            {jobs.recent.map((j) => (
              <div key={j.id} className="q-item">
                <span className="spacer ellipsis">
                  {JOB_TYPE[j.type]} · {j.title}
                  <br />
                  <span className={j.status === 'failed' ? 'error' : 'faint'}>{JOB_LABEL[j.status]}</span>
                </span>
                {j.status === 'done' && (
                  <a className="btn btn-ghost btn-sm" href={`#${RESULT_ROUTE[j.type]}`} onClick={() => setDrawer(false)}>보기</a>
                )}
              </div>
            ))}
          </div>
        </div>
      </aside>

      {toast && (
        <div className="toast" role="status" aria-live="polite">
          {JOB_TYPE[toast.type]}이(가) 끝났어요
          <a className="btn btn-ghost btn-sm" href={`#${RESULT_ROUTE[toast.type]}`} onClick={() => setToast(null)}>보기</a>
        </div>
      )}
    </ShellContext.Provider>
  )
}
