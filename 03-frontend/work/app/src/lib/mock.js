// 백엔드 연결 전 mock. 함수 이름·응답 모양은 api.js의 real과 같다.
// 계약: shared/research/elevenlabs/04-backend-local-api.md §3 (+ 03-frontend-internal-plan.md §4)
// - 줄(lane) 두 개: cpu(tts·transcribe·clone), llm(translate). 줄마다 한 번에 하나씩 처리한다.
// - 텍스트에 '실패'가 들어가면 그 작업은 실패한다(오류 화면 확인용).

export function apiError(code, message) {
  return Object.assign(new Error(message), { code })
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const newId = (p) => `${p}_${++seq}`
const now = () => new Date().toISOString()

const voices = [
  { id: 'ko_f1', name: '기본 여성 1', kind: 'builtin', engine: 'mock', created_at: now() },
  { id: 'ko_m1', name: '기본 남성 1', kind: 'builtin', engine: 'mock', created_at: now() },
]
const jobs = new Map()
const lanes = { cpu: [], llm: [] } // 줄마다 대기·실행 중 job id, 맨 앞이 실행 중
const finished = [] // 최근 끝난 작업 id
const outputs = []
const transcripts = new Map()
const consents = new Map()
const deletedConsents = [] // 지운 목소리의 동의 기록(365일 뒤 삭제 예정)
const nonces = new Map() // nonce → 만료 시각(ms)
const settings = { limit_usd: null } // null = 상한 없음(none). 대표가 기록 화면에서 정한다
const usage = { month: now().slice(0, 7), input_tokens: 0, output_tokens: 0, cache_read_tokens: 0, cache_write_tokens: 0, est_usd: 0 }
const STEP = { tts: 0.07, transcribe: 0.03, translate: 0.1, clone: 0.04 } // 300ms당 진행률
const LANE = { tts: 'cpu', transcribe: 'cpu', clone: 'cpu', translate: 'llm' }

// 상태: queued → preparing(모델 불러오기 1.2초) → running → done/failed/canceled
// 받아쓰기는 엔진이 진행률을 안 준다고 가정(progress=null → 줄무늬 바)
setInterval(() => {
  for (const q of Object.values(lanes)) {
    const job = jobs.get(q[0])
    if (!job) continue
    if (job.cancel_requested) {
      end(job, 'canceled')
      continue
    }
    if (job.status === 'queued') Object.assign(job, { status: 'preparing', ticks: 0, progress: null })
    if (job.status === 'preparing' && ++job.ticks < 4) continue
    job.status = 'running'
    job.done = Math.min(1, (job.done ?? 0) + STEP[job.type])
    job.progress = job.type === 'transcribe' ? null : job.done
    if (job.done >= 1) finish(job)
  }
}, 300)

function enqueue(type, payload) {
  const job = {
    id: newId('job'), type, lane: LANE[type], status: 'queued', progress: 0, cancel_requested: false,
    created_at: now(), result: null, error: null, payload,
  }
  jobs.set(job.id, job)
  lanes[job.lane].push(job.id)
  return { job_id: job.id }
}

function end(job, status) {
  lanes[job.lane].splice(lanes[job.lane].indexOf(job.id), 1)
  finished.push(job.id)
  job.status = status
  job.finished_at = now()
}

function finish(job) {
  const p = job.payload
  if (JSON.stringify(p).includes('실패')) {
    job.error = { code: 'engine_error', message: '음성 엔진 처리 중 오류가 났어요(mock)' }
    return end(job, 'failed')
  }
  if (job.type === 'tts') {
    const sec = Math.max(2, Math.min(20, p.text.length / 7))
    const voice = voices.find((v) => v.id === p.voice_id)
    const o = {
      id: newId('out'), kind: p.kind ?? 'tts', title: p.title || p.text.slice(0, 20), created_at: now(),
      duration_sec: sec, voice_id: p.voice_id, voice_name: voice?.name ?? '', is_clone: voice?.kind === 'clone',
      ai_label: true, files: { [p.format]: true }, _url: toneUrl(sec),
    }
    outputs.unshift(o)
    job.result = { output_id: o.id }
  } else if (job.type === 'transcribe') {
    const t = {
      id: newId('tr'), source_name: p.name, duration_sec: 12, language: p.language,
      source_expires_at: new Date(Date.now() + 30 * 864e5).toISOString(),
      segments: [
        { start: 0, end: 3.2, text: '오늘 회의 시작하겠습니다.' },
        { start: 3.2, end: 7.5, text: '이번 주 영상 내레이션 세 건을 마감해야 합니다.' },
        { start: 7.5, end: 12, text: '자막은 영어와 일본어로 준비합시다.' },
      ],
      translations: {},
    }
    transcripts.set(t.id, t)
    job.result = { transcript_id: t.id }
  } else if (job.type === 'translate') {
    const t = transcripts.get(p.id)
    t.translations[p.lang] = t.segments.map((s) => ({ ...s, text: `[${p.lang}] ${s.text}` }))
    job.result = { transcript_id: t.id, lang: p.lang }
  } else if (job.type === 'clone') {
    const v = { id: newId('voice'), name: p.name, kind: 'clone', engine: 'mock', created_at: now() }
    voices.push(v)
    job.result = { voice_id: v.id }
  }
  end(job, 'done')
}

function view(job) {
  const pos = lanes[job.lane].indexOf(job.id)
  const { payload, ticks, done, ...rest } = job
  return {
    ...rest,
    title: payload.title || payload.name || payload.text?.slice(0, 20) || payload.lang || '',
    queue_position: job.status === 'queued' ? pos : null,
    eta_sec: job.status === 'running' && job.progress != null ? Math.round(((1 - job.done) / STEP[job.type]) * 0.3) : null,
  }
}

function addUsage(inTok, outTok) {
  usage.input_tokens += inTok
  usage.output_tokens += outTok
  usage.cache_read_tokens += Math.round(inTok * 0.6)
  // shortcut: 가상 단가. 실제 금액은 백엔드가 원장으로 계산한다
  usage.est_usd = +(usage.est_usd + inTok * 1e-6 + outTok * 5e-6).toFixed(4)
  return { input_tokens: inTok, output_tokens: outTok, cache_read_tokens: Math.round(inTok * 0.6), est_usd: +(inTok * 1e-6 + outTok * 5e-6).toFixed(4) }
}

function warnLevel() {
  if (!(settings.limit_usd > 0)) return 0
  const r = usage.est_usd / settings.limit_usd
  return r >= 1 ? 100 : r >= 0.8 ? 80 : 0
}

function claudeGate() {
  if (warnLevel() === 100) throw apiError('credit_limit', '이번 달 Claude 한도에 닿았어요')
}

// shortcut: 결과 음성 대신 짧은 신호음(wav). 백엔드 연결 시 실제 파일로 바뀐다.
function toneUrl(sec) {
  const sr = 8000
  const n = Math.round(sr * sec)
  const b = new DataView(new ArrayBuffer(44 + n * 2))
  const w = (o, s) => [...s].forEach((c, i) => b.setUint8(o + i, c.charCodeAt(0)))
  w(0, 'RIFF'); b.setUint32(4, 36 + n * 2, true); w(8, 'WAVEfmt ')
  b.setUint32(16, 16, true); b.setUint16(20, 1, true); b.setUint16(22, 1, true)
  b.setUint32(24, sr, true); b.setUint32(28, sr * 2, true); b.setUint16(32, 2, true); b.setUint16(34, 16, true)
  w(36, 'data'); b.setUint32(40, n * 2, true)
  for (let i = 0; i < n; i++) b.setInt16(44 + i * 2, Math.sin((i / sr) * 2 * Math.PI * 220) * 2000, true)
  return URL.createObjectURL(new Blob([b], { type: 'audio/wav' }))
}

function toSrt(segments) {
  const ts = (s) => new Date(s * 1000).toISOString().slice(11, 23).replace('.', ',')
  return segments.map((s, i) => `${i + 1}\n${ts(s.start)} --> ${ts(s.end)}\n${s.text}\n`).join('\n')
}

const segsOf = (id, lang) => (lang === 'ko' ? transcripts.get(id).segments : transcripts.get(id).translations[lang])
const textUrl = (s) => URL.createObjectURL(new Blob([s], { type: 'text/plain' }))

// ---- 계약 함수 ----
export const getHealth = async () => ({
  ok: true,
  engines: { tts: { name: 'mock', loaded: true }, stt: { name: 'mock', loaded: true }, clone: { name: 'mock', loaded: false } },
  claude_key_present: true,
  ffmpeg: true,
})

export const listVoices = async () => (await wait(100), voices.map((v) => ({ ...v })))

export async function refineScript({ text }) {
  await wait(600)
  if (!text.trim()) throw apiError('bad_format', '대본을 먼저 입력해 주세요')
  claudeGate()
  return { text: text.trim().replace(/\s+/g, ' ') + ' (다듬음·mock)', usage: addUsage(800, 300) }
}

export async function createTts(body) {
  if (!body.text?.trim()) throw apiError('bad_format', '읽을 글을 입력해 주세요')
  if (body.text.length > 5000) throw apiError('too_long', '5,000자까지 한 번에 만들 수 있어요')
  return enqueue('tts', body)
}

export async function getJob(id) {
  const job = jobs.get(id)
  if (!job) throw apiError('not_found', '작업을 찾을 수 없어요')
  return view(job)
}

// GET /api/jobs?active=1&recent=5 → {active, recent(끝난 순 역순)}
export const listJobs = async () => ({
  active: [...lanes.cpu, ...lanes.llm].map((id) => view(jobs.get(id))),
  recent: finished.slice(-5).reverse().map((id) => view(jobs.get(id))),
})

export async function cancelJob(id) {
  const job = jobs.get(id)
  if (!job) return {}
  if (job.status === 'queued') end(job, 'canceled')
  else if (job.status === 'preparing' || job.status === 'running') job.cancel_requested = true // 다음 단계 경계에서 멈춤
  return {}
}

export const transcribe = async (file, language = 'ko') => enqueue('transcribe', { name: file.name, language })

export async function getTranscript(id) {
  const { translations, ...t } = transcripts.get(id)
  return t
}

export async function summarizeTranscript() {
  await wait(600)
  claudeGate()
  return {
    summary: '이번 주 내레이션 3건 마감, 자막은 영어·일본어로 준비한다.',
    decisions: ['자막 언어: 영어, 일본어'],
    todos: ['내레이션 3건 마감'],
    usage: addUsage(1500, 400),
  }
}

export const srtUrl = async (id, lang = 'ko') => textUrl(toSrt(segsOf(id, lang)))
export const txtUrl = async (id, lang = 'ko') => textUrl(segsOf(id, lang).map((s) => s.text).join('\n'))

export async function translateTranscript(id, lang) {
  claudeGate()
  addUsage(1200, 1200)
  return enqueue('translate', { id, lang })
}

export async function summarize({ text, file, length }) {
  await wait(700)
  claudeGate()
  if (file && !/\.(txt|md|pdf)$/i.test(file.name)) throw apiError('bad_format', '.txt, .md, .pdf 파일만 받을 수 있어요')
  const src = file ? `(${file.name}) ` : (text ?? '').trim()
  if (!src) throw apiError('bad_format', '보고서 내용을 넣어 주세요')
  const n = length === 'short' ? 60 : 150
  return { summary: `사장님, 보고 드립니다. ${src.slice(0, n)}… (요약·mock)`, usage: addUsage(2000, 300) }
}

export async function consentSentence() {
  const d = new Date()
  const nonce = newId('nonce')
  const expires = Date.now() + 10 * 60 * 1000
  nonces.set(nonce, expires)
  const code = String(1000 + Math.floor(Math.random() * 9000))
  return {
    nonce,
    expires_at: new Date(expires).toISOString(),
    sentence: `저는 ${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일, 사내 음성 도구에서 제 목소리를 복제하는 것에 동의합니다. 확인 번호 ${code}.`,
  }
}

export async function saveConsent({ owner, nonce, audio, consent_doc, subject_name }) {
  await wait(300)
  if (!(nonces.get(nonce) > Date.now())) throw apiError('nonce_expired', '동의 문장이 만료됐어요. 새 문장을 받아 다시 읽어 주세요')
  if (!audio) throw apiError('consent_required', '동의 낭독 녹음이 필요해요')
  if (owner === 'other' && (!consent_doc || !subject_name?.trim()))
    throw apiError('consent_required', '다른 사람의 목소리는 이름과 동의서 파일이 필요해요')
  nonces.delete(nonce) // 1회용
  const id = newId('consent')
  consents.set(id, { owner, used: false, at: now() })
  return { consent_id: id }
}

export async function cloneVoice({ name, consent_id, files }) {
  const c = consents.get(consent_id)
  if (!c) throw apiError('consent_required', '동의 기록이 없어 복제할 수 없어요')
  if (c.used) throw apiError('consent_used', '이 동의로는 이미 목소리를 만들었어요. 새로 동의를 받아 주세요')
  if (!name?.trim()) throw apiError('bad_format', '목소리 이름을 입력해 주세요')
  c.used = true
  return enqueue('clone', { name, n: files.length })
}

export async function deleteVoice(id) {
  const i = voices.findIndex((v) => v.id === id && v.kind === 'clone')
  if (i >= 0) {
    const [v] = voices.splice(i, 1)
    const purge = new Date(Date.now() + 365 * 864e5)
    deletedConsents.push({ id: newId('consent'), voice_name: v.name, voice_deleted_at: now(), purge_at: purge.toISOString() })
  }
  return {}
}

export const listConsents = async () => deletedConsents.map((c) => ({ ...c }))

export const listOutputs = async () => outputs.map((o) => ({ ...o }))
export const audioUrl = (o) => o._url
export const downloadUrl = (o) => o._url

export async function deleteOutput(id) {
  const i = outputs.findIndex((o) => o.id === id)
  if (i >= 0) outputs.splice(i, 1)
  return {}
}

export const getUsage = async () => ({ ...usage, limit_usd: settings.limit_usd, warn_level: warnLevel() })
export const usageCsvUrl = () => textUrl(`month,input_tokens,output_tokens,est_usd\n${usage.month},${usage.input_tokens},${usage.output_tokens},${usage.est_usd}\n`)

export async function saveSettings({ limit_usd }) {
  if (limit_usd != null && !(Number(limit_usd) >= 0)) throw apiError('bad_format', '상한은 0 이상의 숫자로 입력해 주세요')
  settings.limit_usd = limit_usd == null ? null : Number(limit_usd)
  return { ...settings }
}
