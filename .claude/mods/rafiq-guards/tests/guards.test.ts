import { expect, test } from 'claude-code/testing'

const SETTINGS = JSON.stringify({
  hooks: {
    PreToolUse: [
      { matcher: 'Bash', hooks: [{ type: 'command', command: 'node "$CLAUDE_PROJECT_DIR/.claude/hooks/guard-paid-actions.cjs"' }] },
    ],
  },
})

// يقف مكان المحرّك: قراءة الإعدادات، وتشغيل الحارس (يرفض كل gh workflow run)، وgit status.
function engine(on: any, seen: string[] = []) {
  on('command.register', () => ({ value: { command: 'rafiq-guards' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('fs.read', (_: any, e: any) =>
    e.path.endsWith('/.claude/settings.json') ? { value: SETTINGS } : { deny: 'لا ملف' },
  )
  on('process.run', (_: any, e: any) => {
    const argv: string[] = [...e.argv]
    seen.push(argv.join(' '))
    if (argv[0] === 'sh' && String(argv[2]).startsWith('ls -d')) {
      return { value: { exitCode: 0, stdout: '/home/user/QuranRafiq/.claude/settings.json\n/home/user/other/.claude/settings.json\n', stderr: '' } }
    }
    if (argv[0] === 'sh') {
      const input = JSON.parse(e.init?.stdin ?? '{}')
      const bad = /gh workflow run/.test(input.tool_input?.command ?? '')
      return { value: { exitCode: bad ? 2 : 0, stdout: '', stderr: bad ? 'حارس الإنفاق: تشغيلة مدفوعة' : '' } }
    }
    if (argv[0] === 'git') return { value: { exitCode: 0, stdout: ' M app/a.kt\n?? docs/b.md\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: '/home/user\n', stderr: '' } }
  })
  on('tool.call', () => ({ result: {} }))
}

test('رسالة خيط إنجليزية تُردّ والعربية تمرّ', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/home/user', surface: 'mobile', isInteractive: true })
  const en = await $.tool.call({ tool: 'mcp__hearthbot__post_message', text: 'The build passed and the PR is ready for review now.' } as any)
  expect(String((en as any).deny)).toContain('حارس العربية')
  const ar = await $.tool.call({ tool: 'mcp__hearthbot__post_message', text: 'نجح البناء وطلب الدمج جاهز في `app/build.gradle`.' } as any)
  expect((ar as any).deny).toBe(undefined)
})

test('رسالة إيداع بلا عربية تُردّ', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/home/user', surface: 'mobile', isInteractive: true })
  const en = await $.tool.call({ tool: 'Bash', command: 'git commit -m "fix the crash" -- app/a.kt', description: 'إيداع' })
  expect(String((en as any).deny)).toContain('رسالة الإيداع')
  const ar = await $.tool.call({ tool: 'Bash', command: 'git commit -m "إصلاح الانهيار في `Foo`" -- app/a.kt', description: 'إيداع' })
  expect((ar as any).deny).toBe(undefined)
})

test('git add -A يُردّ ومعه الملفات المتغيرة', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/home/user', surface: 'mobile', isInteractive: true })
  const r = await $.tool.call({ tool: 'Bash', command: 'cd x && git add -A && git commit -m "تحديث"', description: 'إيداع' })
  const deny = String((r as any).deny)
  expect(deny).toContain('حارس الإيداع')
  expect(deny).toContain('app/a.kt')
  const ok = await $.tool.call({ tool: 'Bash', command: 'git add app/a.kt', description: 'إضافة ملف' })
  expect((ok as any).deny).toBe(undefined)
})

test('الجسر يشغّل حارس المستودع خارج المستودع', async ($, on) => {
  const seen: string[] = []
  engine(on, seen)
  await $.session.start({ cwd: '/home/user', surface: 'mobile', isInteractive: true })
  const r = await $.tool.call({ tool: 'Bash', command: 'gh workflow run build.yml', description: 'تشغيل' })
  expect(String((r as any).deny)).toContain('حارس الإنفاق')
  expect(seen.some(s => s.includes('/.claude/hooks/guard-paid-actions.cjs') && !s.includes('$CLAUDE_PROJECT_DIR'))).toBe(true)
  // الحارس نفسه في مستودعين يُشغَّل مرة واحدة.
  expect(seen.filter(s => s.startsWith('sh -c node')).length).toBe(1)
})

test('ذكر الأمر داخل نص مقتبس لا يُمنع', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/home/user', surface: 'mobile', isInteractive: true })
  const r = await $.tool.call({ tool: 'Bash', command: "printf 'cd x && git add -A . then report' > p.txt", description: 'كتابة ملف' })
  expect((r as any).deny).toBe(undefined)
})

test('داخل المستودع لا يتكرر الحارس', async ($, on) => {
  const seen: string[] = []
  engine(on, seen)
  await $.session.start({ cwd: '/home/user/QuranRafiq', surface: 'terminal', isInteractive: true })
  const r = await $.tool.call({ tool: 'Bash', command: 'gh workflow run build.yml', description: 'تشغيل' })
  expect((r as any).deny).toBe(undefined)
  expect(seen.some(s => s.startsWith('sh -c node'))).toBe(false)
})
