import { useState } from 'react'
import { api } from '../lib/api.js'

const KIND = { tts: '내레이션', briefing: '브리핑', transcript: '받아쓰기' }

// 파일명 규칙(디자인 02 §2-1): YYYYMMDD-HHMM_종류_제목_AI.ext.
// 실서버는 Content-Disposition 파일명이 우선한다(복제 음성은 _AI-clone, 백엔드 §5). 이 이름은 mock용 대체값.
function fileName(o) {
  const d = new Date(o.created_at)
  const p = (n) => String(n).padStart(2, '0')
  const stamp = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
  const title = (o.title || '').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 30)
  return `${stamp}_${KIND[o.kind] ?? o.kind}_${title}_AI.${o.files?.wav ? 'wav' : 'mp3'}`
}

/** 결과 플레이어: 재생, AI 생성 배지, 설명란 문구 복사, 내려받기 (+ 기록 화면에서는 삭제 버튼을 children으로) */
export default function ResultCard({ output, children }) {
  const [copied, setCopied] = useState(false)
  const src = api.audioUrl(output)
  const desc = `이 콘텐츠의 음성은 AI로 생성했습니다.${output.is_clone ? ' 목소리 주인의 동의를 받아 복제한 음성입니다.' : ''}`

  async function copy() {
    await navigator.clipboard.writeText(desc)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="result-card">
      <div className="row">
        <strong className="ellipsis">{output.title}</strong>
        {output.ai_label ? (
          <span className="badge badge-ai">✦ AI 생성</span>
        ) : (
          <span className="badge badge-warn" role="alert">AI 표시 누락</span>
        )}
        {output.is_clone && <span className="badge badge-clone">복제 음성</span>}
      </div>
      <div className="row faint">
        <span>{KIND[output.kind] ?? output.kind}</span>
        <span className="mono">{new Date(output.created_at).toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' })}</span>
        {output.voice_name && <span>{output.voice_name}</span>}
        {output.source_expires_at && <span>원본 {output.source_expires_at.slice(0, 10)} 삭제 예정</span>}
      </div>
      {/* shortcut: 시안의 원형 재생 버튼+파형(.player .wave)은 기본 <audio>로 대신함, 파형 데이터 API가 생기면 교체 */}
      <audio controls preload="metadata" src={src} />
      <div className="foot">
        <button className="btn btn-ghost" onClick={copy} aria-live="polite">
          {copied ? '복사됨' : '설명란 문구 복사'}
        </button>
        <span className="spacer" />
        <a className="btn btn-ghost" href={api.downloadUrl(output)} download={fileName(output)}>
          내려받기
        </a>
        {children}
      </div>
    </div>
  )
}
