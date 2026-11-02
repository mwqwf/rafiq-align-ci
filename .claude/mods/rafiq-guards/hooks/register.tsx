// 🛡️ مود حرّاس مصحفك (أمر المالك 2026-11-02).
// العلّة: خيوط المشروع السحابية تبدأ في /home/user لا في المستودع، فلا تُحمَّل هوكات
// .claude/settings.json فيها، وحرّاس الإنفاق والأصول والعربية غائبون عنها.
// فالمود (يُحمَّل بـCLAUDE_CODE_PLUGIN_DIRS أياً كان مجلد البدء):
//   ١. يجسر هوكات PreToolUse من إعدادات المستودع فيشغّلها كما هي، إن لم تكن الجلسة داخله أصلاً.
//   ٢. يفرض العربية فيما يراه المالك: رسائل الخيط وطلبات الدمج وتعليقات GitHub ورسائل الإيداع.
//   ٣. يمنع git add -A و git commit -a ويعيد معه قائمة الملفات المتغيرة فلا تضيع محاولة.
//   ٤. لوحة «حرّاس رفيق» وأمر /rafiq-guards يعرضان ما رُدّ في الجلسة.
import { atom, read, update } from 'claude-code'
import type { Register, EngineInterface } from 'claude-code'

import type { Denial } from '../types'
import {
  bulkAddMessage,
  bulkAddProblem,
  classicVerdict,
  commitMessageProblem,
  matcherHits,
  ownerTextProblem,
} from './rules'

const PANE = 'rafiq-guards'
const FALLBACK_HOME = '/home/user'
const denials = atom({ plugin: 'rafiq-guards', key: 'denials' } as const, [], { shape: 'denials-1' })

type Bridged = { matcher?: string; command: string; root: string }

// حالة الوحدة (تُعاد مع كل تحميل، و session.start يعيد ملأها).
let bridged: Bridged[] = []
let bridgeActive = false
let roots: string[] = []

const RESERVED = new Set(['tool', 'tool_use_id', 'consent', 'agentId', 'parentAgentId', 'agentType'])

async function readText($: EngineInterface, path: string): Promise<string | undefined> {
  try {
    return await $.fs.read(path)
  } catch {
    try {
      const r = await $.process.run(['cat', path], { timeoutMs: 5000 })
      return r.exitCode === 0 ? r.stdout : undefined
    } catch {
      return undefined
    }
  }
}

// كل مستودع مستنسخ في /home/user (وفي مستودع المود نفسه) تُجسَر هوكاته، إلا ما كانت الجلسة داخله
// فهو يشغّلها بنفسه. ويُكتفى بأول نسخة من كل حارس باسم ملفه فلا يتكرر حارس مشترك بين مستودعين.
async function loadBridge($: EngineInterface, cwd: string) {
  const fromPlugin = $.plugin.root.replace(/\/\.claude\/mods\/[^/]+\/?$/, '')
  let listed: string[] = []
  try {
    const r = await $.process.run(['sh', '-c', `ls -d ${FALLBACK_HOME}/*/.claude/settings.json 2>/dev/null`], { timeoutMs: 5000 })
    listed = r.stdout.split('\n').filter(Boolean).map(f => f.replace(/\/\.claude\/settings\.json$/, ''))
  } catch {
    /* لا مستودعات */
  }
  const inside = (root: string) => cwd === root || cwd.startsWith(root + '/')
  const seen = new Set<string>()
  bridged = []
  roots = []
  // نسخة المود المستنسخة خارج /home/user (من سكربت الإعداد) ليست مستودع عمل فلا تُجسر هوكاتها.
  const own = fromPlugin.startsWith(FALLBACK_HOME + '/') ? [fromPlugin] : []
  for (const root of [...new Set([...own, ...listed])]) {
    const raw = await readText($, `${root}/.claude/settings.json`)
    if (!raw) continue
    let pre: { matcher?: string; hooks?: { type: string; command: string }[] }[] = []
    try {
      pre = JSON.parse(raw).hooks?.PreToolUse ?? []
    } catch {
      continue
    }
    const mine = pre.flatMap(g => (g.hooks ?? []).filter(h => h.type === 'command').map(h => ({ matcher: g.matcher, command: h.command, root })))
    for (const h of mine) {
      const id = (h.command.match(/([\w.-]+\.c?js)/) ?? [])[1] ?? h.command
      if (seen.has(id)) continue
      seen.add(id) // داخل المستودع: يُحسب الحارس مشغَّلاً فلا يُجسر من غيره أيضاً.
      if (!inside(root)) bridged.push(h)
    }
    if (mine.length && !inside(root)) roots.push(root)
  }
  bridgeActive = bridged.length > 0
}

async function note($: EngineInterface, tool: string, guard: string, reason: string) {
  const d: Denial = { at: new Date().toISOString().slice(11, 19), tool, guard, reason: reason.slice(0, 300) }
  await update($, denials, list => [...list, d].slice(-50))
}

// يشغّل هوكاً كلاسيكياً: الأمر نفسه عبر sh بعد تعويض $CLAUDE_PROJECT_DIR.
async function runClassic($: EngineInterface, h: Bridged, toolName: string, toolInput: Record<string, unknown>, cwd: string) {
  const command = h.command.replace(/\$\{?CLAUDE_PROJECT_DIR\}?/g, h.root)
  const stdin = JSON.stringify({
    hook_event_name: 'PreToolUse',
    tool_name: toolName,
    tool_input: toolInput,
    cwd,
    session_id: 'rafiq-guards-bridge',
  })
  try {
    const r = await $.process.run(['sh', '-c', command], {
      stdin,
      env: { CLAUDE_PROJECT_DIR: h.root },
      timeoutMs: 15000,
    })
    return classicVerdict(r.exitCode, r.stdout, r.stderr)
  } catch {
    return undefined // خلل في تشغيل الحارس لا يعطّل العمل، كما تفعل الهوكات نفسها.
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await loadBridge($, e.cwd)
    await $.command.register({ name: 'rafiq-guards', description: 'يعرض حرّاس مصحفك وما ردّوه في هذه الجلسة' })
    return next(e)
  })

  on('command.run', { command: 'rafiq-guards' }, async $ => {
    const list = await read($, denials)
    void $.ui.open({ id: PANE, title: 'حرّاس رفيق' })
    const head = `الجسر ${bridgeActive ? `يعمل (${bridged.length} حارساً من ${roots.join('، ')})` : 'مطفأ: الجلسة داخل المستودع أو لا إعدادات'}.`
    return { text: [head, `المردود في الجلسة: ${list.length}.`, ...list.slice(-5).map(d => `${d.at} ${d.tool}: ${d.reason.split('\n')[0]}`)].join('\n') }
  })

  on('tool.call', async ($, e, next) => {
    const input: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(e)) if (!RESERVED.has(k)) input[k] = v
    const tool = String(e.tool)

    // ٢. العربية فيما يراه المالك.
    const owner = ownerTextProblem(tool, input)
    if (owner) {
      await note($, tool, 'العربية', owner)
      return { deny: owner }
    }

    if (tool === 'Bash' && typeof input.command === 'string') {
      const cmd = input.command
      const commit = commitMessageProblem(cmd)
      if (commit) {
        await note($, tool, 'العربية', commit)
        return { deny: commit }
      }
      // ٣. الإيداع بالجملة.
      const bulk = bulkAddProblem(cmd)
      if (bulk) {
        let porcelain = ''
        try {
          porcelain = (await $.process.run(['git', 'status', '--porcelain'], { timeoutMs: 5000 })).stdout
        } catch {
          /* خارج مستودع: القائمة فارغة */
        }
        const msg = bulkAddMessage(bulk, porcelain)
        await note($, tool, 'الإيداع', msg)
        return { deny: msg }
      }
    }

    // ١. جسر هوكات المستودع (بالتوازي).
    if (bridgeActive) {
      const hits = bridged.filter(h => matcherHits(h.matcher, tool))
      if (hits.length) {
        const cwd = (await $.process.run(['pwd'], { timeoutMs: 3000 }).catch(() => ({ stdout: FALLBACK_HOME }))).stdout.trim()
        const verdicts = await Promise.all(hits.map(h => runClassic($, h, tool, input, cwd)))
        const i = verdicts.findIndex(v => v !== undefined)
        if (i >= 0) {
          const guard = (hits[i]!.command.match(/hooks\/([\w-]+)\.cjs/) ?? [])[1] ?? 'حارس'
          await note($, tool, guard, verdicts[i]!)
          return { deny: verdicts[i]! }
        }
      }
    }

    return next(e)
  }).catch(($, e, next) => next(e)) // خللٌ في المود لا يعطّل العمل، كالهوكات

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, denials)
    return (
      <Box flexDirection="column">
        <Text bold dir="rtl">
          {bridgeActive ? `الجسر يعمل: ${bridged.length} حارساً` : 'الجسر مطفأ (الجلسة داخل المستودع)'}
        </Text>
        {list.length === 0 && <Text dimColor dir="rtl">لم يُردّ شيء بعد في هذه الجلسة.</Text>}
        {list.slice(-15).map(d => (
          <Text dir="rtl">
            {d.at} · {d.guard} · {d.tool}: {(d.reason.split('\n')[0] ?? '').slice(0, 120)}
          </Text>
        ))}
      </Box>
    )
  })
}
