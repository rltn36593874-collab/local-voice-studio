// 디자인 시안(02-design/work/mockup)의 tokens.css + index.html <style>을 src/design.css로 복사한다.
// 시안이 바뀌면 `npm run sync-design`만 다시 돌린다.
import { readFileSync, writeFileSync } from 'node:fs'
const dir = new URL('../../../../02-design/work/mockup/', import.meta.url)
const tokens = readFileSync(new URL('tokens.css', dir), 'utf8')
const html = readFileSync(new URL('index.html', dir), 'utf8')
const style = html.match(/<style>\n?([\s\S]*?)<\/style>/)?.[1]
if (!style) throw new Error('시안 index.html에서 <style> 블록을 찾지 못했어요')
const head = '/* 디자인팀 시안 그대로 복사 — 손으로 고치지 말 것. 갱신: npm run sync-design\n   원본: 02-design/work/mockup/tokens.css + index.html <style> */\n'
writeFileSync(new URL('../src/design.css', import.meta.url), head + tokens + '\n' + style)
console.log('src/design.css 갱신 완료')
