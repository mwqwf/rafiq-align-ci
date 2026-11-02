// قواعد الحراس الخالصة (بلا $): تُختبر وحدها، ويستدعيها register.tsx.

const AR = /[؀-ۿ]/g
const LAT = /[A-Za-z]/g
const count = (s: string, re: RegExp) => (s.match(re) || []).length

// يحذف ما يُستثنى من شرط العربية: الشيفرة والروابط والمسارات وأرقام الطلبات.
export function strip(t: string): string {
  return t
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`\n]*`/g, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/(?:[\w.-]+\/)+[\w.-]+/g, ' ')
    .replace(/#\d+/g, ' ')
    .replace(/\bcmsg_\w+/g, ' ')
}

// المعيار نفسه في .claude/hooks/arabic-only.cjs: اللاتينية تغلب إذا بلغت 15 حرفاً وزادت على خُمس العربية.
export function latinHeavy(text: string): boolean {
  const t = strip(text)
  const ar = count(t, AR)
  const lat = count(t, LAT)
  return lat >= 15 && lat > ar * 0.2
}

export const hasArabic = (s: string) => count(s, AR) > 0

// نصوص يراها المالك في أدوات الخيط وGitHub: اسم الأداة ← الحقول.
export const OWNER_TEXT_FIELDS: Record<string, string[]> = {
  mcp__hearthbot__post_message: ['text'],
  mcp__hearthbot__request_decision: ['question'],
  mcp__hearthbot__update_progress_checklist: ['text'],
  mcp__hearthbot__message_coordinator: [],
  mcp__github__create_pull_request: ['title', 'body'],
  mcp__github__update_pull_request: ['title', 'body'],
  mcp__github__add_issue_comment: ['body'],
  mcp__github__add_reply_to_pull_request_comment: ['body'],
}

export function ownerTextProblem(tool: string, input: Record<string, unknown>): string | undefined {
  const fields = OWNER_TEXT_FIELDS[tool]
  if (!fields) return undefined
  for (const f of fields) {
    const v = input[f]
    if (typeof v !== 'string' || !v.trim()) continue
    // العنوان قصير: يكفي فيه حرف عربي؛ وما سواه يُحكم بغلبة اللاتينية.
    const bad = f === 'title' ? !hasArabic(v) : latinHeavy(v)
    if (bad) {
      return `حارس العربية: الحقل «${f}» يراه المالك وأغلبه بالإنجليزية. أعد كتابته بالعربية، وأبقِ أسماء الشيفرة داخل \`…\`.`
    }
  }
  return undefined
}

// رسالة الإيداع في أمر git commit -m "…": يلزمها حرف عربي.
export function commitMessageProblem(cmd: string): string | undefined {
  if (!/\bgit\b[^\n;&|]*\bcommit\b/.test(cmd)) return undefined
  const msgs: string[] = []
  const re = /(?:-m|--message)(?:=|\s+)(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|\$\(cat\s+<<-?\s*['"]?(\w+)['"]?\n([\s\S]*?)\n\s*\3\s*\))/g
  let m: RegExpExecArray | null
  while ((m = re.exec(cmd))) msgs.push(m[1] ?? m[2] ?? m[4] ?? '')
  if (!msgs.length) return undefined
  const subject = (msgs[0] ?? '').split('\n')[0] ?? ''
  if (hasArabic(subject)) return undefined
  return 'حارس العربية: سطر عنوان رسالة الإيداع بلا حرف عربي. اكتبه بالعربية (أسماء الشيفرة تبقى بصيغتها).'
}

// git add -A / --all / . و git commit -a: الشجرة مشتركة بين الجلسات فالإيداع بمسار صريح.
export function bulkAddProblem(cmd: string): string | undefined {
  // الأفعال لا الألفاظ: تُزال أجسام heredoc والسلاسل المقتبسة قبل المطابقة، فلا يُمنع نصٌّ يذكر الأمر
  // (إيجابية كاذبة مقيسة 2026-11-02: printf يكتب الأمر في ملف).
  const acts = cmd
    .replace(/<<-?\s*['"]?(\w+)['"]?[\s\S]*?\n\s*\1\b/g, ' ')
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')
    .replace(/'[^']*'/g, "''")
  for (const seg of acts.split(/&&|\|\||;|\n|\|/)) {
    const s = seg.trim()
    if (/^git(\s+-C\s+\S+)?\s+add\b/.test(s)) {
      const args = s.replace(/^git(\s+-C\s+\S+)?\s+add\b/, '').trim().split(/\s+/)
      if (args.some(a => a === '-A' || a === '--all' || a === '.' || a === ':/'))
        return 'bulk-add'
    }
    if (/^git(\s+-C\s+\S+)?\s+commit\b/.test(s)) {
      const args = s.split(/\s+/)
      if (args.some(a => a === '-a' || a === '--all' || /^-[a-zA-Z]*a[a-zA-Z]*$/.test(a) && !a.startsWith('--') && a !== '-m'))
        return 'bulk-commit'
    }
  }
  return undefined
}

export function bulkAddMessage(kind: string, porcelain: string): string {
  const files = porcelain.split('\n').filter(Boolean).slice(0, 30).map(l => l.slice(3))
  const what = kind === 'bulk-add' ? '`git add -A` أو `git add .`' : '`git commit -a`'
  return (
    `حارس الإيداع: ${what} ممنوع، فالشجرة مشتركة بين الجلسات. أضف المسارات صراحة ثم أودع بـ\`git commit -m … -- <المسارات>\`.` +
    (files.length ? `\nالملفات المتغيرة الآن:\n${files.join('\n')}` : '')
  )
}

// ترجمة مُطابِق هوك الإعدادات ("Bash|Agent") إلى اختبار لاسم الأداة.
export function matcherHits(matcher: string | undefined, tool: string): boolean {
  if (!matcher || matcher === '*') return true
  try {
    return new RegExp(`^(?:${matcher})$`).test(tool)
  } catch {
    return matcher === tool
  }
}

// قراءة ردّ هوك من النمط الكلاسيكي: exit 2 مع stderr، أو JSON بقرار deny.
export function classicVerdict(exitCode: number, stdout: string, stderr: string): string | undefined {
  if (exitCode === 2) return stderr.trim() || 'رفضه حارس بلا سبب مكتوب.'
  const out = stdout.trim()
  if (!out.startsWith('{')) return undefined
  try {
    const j = JSON.parse(out)
    const h = j.hookSpecificOutput
    if (h && h.permissionDecision === 'deny') return String(h.permissionDecisionReason || 'رفضه حارس.')
    if (j.decision === 'block') return String(j.reason || 'رفضه حارس.')
  } catch {
    /* ليس JSON: لا حكم */
  }
  return undefined
}
