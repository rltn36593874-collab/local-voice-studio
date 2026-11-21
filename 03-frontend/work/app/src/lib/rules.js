// 복제 샘플 규칙. 근거: 01-planning-internal-mvp.md §3, 03-frontend-client-logic.md §1-2.
// 서버도 같은 규칙으로 다시 검사한다(클라이언트 검사는 안내용).
export const LIMITS = {
  maxFileBytes: 10 * 1024 * 1024,
  minFileSec: 5,
  minTotalSec: 10,
  maxTotalSec: 180,
}

export const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm']

/** 브라우저가 지원하는 첫 녹음 MIME. 없으면 ''(브라우저 기본값 사용) */
export function pickMimeType(isSupported) {
  return MIME_CANDIDATES.find((t) => isSupported(t)) ?? ''
}

/** 파일 한 개 검사. 문제 없으면 null */
export function checkFile({ size, durationSec }) {
  if (size > LIMITS.maxFileBytes)
    return { code: 'file_too_large', message: `10MB를 넘는 파일이에요(${(size / 1048576).toFixed(1)}MB)` }
  if (durationSec == null || Number.isNaN(durationSec))
    return { code: 'bad_format', message: '파일을 열 수 없어요. MP3·WAV·M4A를 올려 주세요' }
  if (durationSec < LIMITS.minFileSec)
    return { code: 'too_short', message: '이 파일은 5초보다 짧아 쓸 수 없어요' }
  return null
}

/** 샘플 합계 검사. 문제 없으면 null */
export function checkTotal(totalSec) {
  if (totalSec < LIMITS.minTotalSec)
    return { code: 'too_short', message: `최소 10초가 필요해요. ${Math.ceil(LIMITS.minTotalSec - totalSec)}초 더 녹음해 주세요` }
  if (totalSec > LIMITS.maxTotalSec)
    return { code: 'too_long', message: `합계가 3분을 넘었어요. 샘플을 빼 주세요(지금 ${fmtSec(totalSec)})` }
  return null
}

/**
 * Claude 사용량 화면 단계(디자인 02 §2-3, 대표 결정 11-22): none | ok | warn | over
 * none = 월 상한 미입력(금액만 표시). 서버 warn_level(80·100)을 우선하고, 없으면 금액으로 계산한다.
 */
export function usageLevel(usage) {
  if (!usage || !(usage.limit_usd > 0)) return 'none'
  const w = usage.warn_level ?? (usage.est_usd / usage.limit_usd) * 100
  return w >= 100 ? 'over' : w >= 80 ? 'warn' : 'ok'
}

/** 오늘부터 days일 뒤 날짜(YYYY-MM-DD). 보관 기간 안내용 */
export function dateAfter(days, from = new Date()) {
  const d = new Date(from)
  d.setDate(d.getDate() + days)
  return d.toLocaleDateString('sv-SE') // YYYY-MM-DD(로컬 날짜)
}

export function fmtSec(sec) {
  const s = Math.max(0, Math.floor(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
