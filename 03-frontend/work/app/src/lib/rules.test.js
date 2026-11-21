import { test } from 'node:test'
import assert from 'node:assert/strict'
import { checkFile, checkTotal, fmtSec, pickMimeType, usageLevel, dateAfter, LIMITS } from './rules.js'

test('checkFile: 용량·형식·길이', () => {
  assert.equal(checkFile({ size: LIMITS.maxFileBytes, durationSec: 5 }), null)
  assert.equal(checkFile({ size: LIMITS.maxFileBytes + 1, durationSec: 30 }).code, 'file_too_large')
  assert.equal(checkFile({ size: 1000, durationSec: NaN }).code, 'bad_format')
  assert.equal(checkFile({ size: 1000, durationSec: 4.9 }).code, 'too_short')
})

test('checkTotal: 10초~3분 경계', () => {
  assert.equal(checkTotal(9.9).code, 'too_short')
  assert.match(checkTotal(3).message, /7초 더/)
  assert.equal(checkTotal(10), null)
  assert.equal(checkTotal(180), null)
  assert.equal(checkTotal(180.5).code, 'too_long')
})

test('usageLevel: 상한 없으면 none, 80·100% 경계, 서버 warn_level 우선', () => {
  assert.equal(usageLevel(null), 'none')
  assert.equal(usageLevel({ est_usd: 99, limit_usd: null }), 'none')
  assert.equal(usageLevel({ est_usd: 31.9, limit_usd: 40 }), 'ok')
  assert.equal(usageLevel({ est_usd: 32, limit_usd: 40 }), 'warn')
  assert.equal(usageLevel({ est_usd: 40, limit_usd: 40 }), 'over')
  assert.equal(usageLevel({ est_usd: 0, limit_usd: 40, warn_level: 100 }), 'over')
  assert.equal(usageLevel({ est_usd: 39, limit_usd: 40, warn_level: 50 }), 'ok') // 50 단계는 없앰
})

test('dateAfter: 365일 뒤', () => {
  assert.equal(dateAfter(365, new Date(2026, 10, 22)), '2027-11-22')
  assert.equal(dateAfter(30, new Date(2026, 10, 22)), '2026-12-22')
})

test('fmtSec, pickMimeType', () => {
  assert.equal(fmtSec(0), '0:00')
  assert.equal(fmtSec(204.9), '3:24')
  assert.equal(pickMimeType((t) => t === 'audio/mp4'), 'audio/mp4') // 사파리
  assert.equal(pickMimeType(() => false), '')
})
