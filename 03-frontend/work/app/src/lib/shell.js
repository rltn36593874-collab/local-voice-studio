import { createContext, useContext } from 'react'

// 앱 셸이 모든 화면에 내려 주는 공용 상태: Claude 사용량({usage, level, refreshUsage}), 작업 목록 갱신 신호
export const ShellContext = createContext({ usage: null, level: 'ok', refreshUsage() {}, pokeJobs() {} })
export const useShell = () => useContext(ShellContext)

export const JOB_LABEL = { queued: '대기 중', preparing: '준비 중', running: '처리 중', done: '완료', failed: '실패', canceled: '취소됨' }
export const JOB_TYPE = { tts: '음성 생성', transcribe: '받아쓰기', translate: '자막 번역', clone: '목소리 복제' }
export const isActive = (s) => s === 'queued' || s === 'preparing' || s === 'running'
