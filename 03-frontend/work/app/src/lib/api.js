// 로컬 백엔드 API. 계약: shared/research/elevenlabs/03-frontend-internal-plan.md §4
// 기본은 mock, `npm run dev:real`일 때만 실제 서버(:8000, vite 프록시).
import * as mock from './mock.js'

export const IS_MOCK = import.meta.env.VITE_API !== 'real'

async function http(path, { method = 'GET', json, form } = {}) {
  let res
  try {
    res = await fetch(path, {
      method,
      headers: json ? { 'Content-Type': 'application/json' } : undefined,
      body: json ? JSON.stringify(json) : form,
    })
  } catch {
    throw mock.apiError('network', '로컬 서버에 연결할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요')
  }
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null
  if (!res.ok) throw mock.apiError(data?.error?.code ?? `http_${res.status}`, data?.error?.message ?? `서버 오류(${res.status})`)
  return data
}

function formOf(obj) {
  const f = new FormData()
  for (const [k, v] of Object.entries(obj)) {
    if (v == null) continue
    if (Array.isArray(v)) v.forEach((x) => f.append(k, x))
    else f.append(k, v)
  }
  return f
}

// 계약: 04-backend-local-api.md §3 (합의 2026-11-22)
const real = {
  getHealth: () => http('/api/health'),
  listVoices: () => http('/api/voices'),
  refineScript: (body) => http('/api/script/refine', { method: 'POST', json: body }),
  createTts: (body) => http('/api/tts', { method: 'POST', json: body }),
  getJob: (id) => http(`/api/jobs/${id}`),
  listJobs: () => http('/api/jobs?active=1&recent=5'), // → {active, recent}
  cancelJob: (id) => http(`/api/jobs/${id}`, { method: 'DELETE' }),
  transcribe: (file, language = 'ko') => http('/api/transcribe', { method: 'POST', form: formOf({ file, language }) }),
  getTranscript: (id) => http(`/api/transcripts/${id}`),
  summarizeTranscript: (id) => http(`/api/transcripts/${id}/summary`, { method: 'POST' }),
  srtUrl: async (id, lang = 'ko') => `/api/transcripts/${id}/srt?lang=${encodeURIComponent(lang)}`,
  txtUrl: async (id, lang = 'ko') => `/api/transcripts/${id}/txt?lang=${encodeURIComponent(lang)}`,
  translateTranscript: (id, lang) => http(`/api/transcripts/${id}/translate`, { method: 'POST', json: { lang } }),
  // 파일이 있으면 multipart(.txt·.md·.pdf), 없으면 JSON
  summarize: ({ text, file, length }) =>
    file
      ? http('/api/summarize', { method: 'POST', form: formOf({ file, length }) })
      : http('/api/summarize', { method: 'POST', json: { text, length } }),
  consentSentence: () => http('/api/consents/sentence'),
  listConsents: () => http('/api/consents'), // [{id, voice_name, voice_deleted_at, purge_at}]
  saveConsent: (fields) => http('/api/consents', { method: 'POST', form: formOf(fields) }),
  cloneVoice: (fields) => http('/api/voices/clone', { method: 'POST', form: formOf(fields) }),
  deleteVoice: (id) => http(`/api/voices/${id}`, { method: 'DELETE' }),
  listOutputs: () => http('/api/outputs'),
  audioUrl: (o) => `/api/outputs/${o.id}/audio`,
  downloadUrl: (o) => `/api/outputs/${o.id}/download?format=${o.files?.wav ? 'wav' : 'mp3'}`,
  deleteOutput: (id) => http(`/api/outputs/${id}`, { method: 'DELETE' }),
  getUsage: () => http('/api/usage'),
  usageCsvUrl: () => '/api/usage/export.csv',
  saveSettings: (body) => http('/api/settings', { method: 'PUT', json: body }),
}

export const api = IS_MOCK ? mock : real

// 계약 점검: real에 있는 함수가 mock에 없으면 개발 중 콘솔에 알린다
if (import.meta.env.DEV) {
  const missing = Object.keys(real).filter((k) => typeof mock[k] !== 'function')
  if (missing.length) console.warn('[api] mock에 없는 계약 함수:', missing)
}
