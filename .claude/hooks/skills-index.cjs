#!/usr/bin/env node
/**
 * فهرس المهارات الإلزاميّ — SessionStart.
 *
 * أمر المالك 2026-11-01: «اجعل الوكلاء يرجعون إلى المهارة المناسبة عند الحاجة… رأيتُ أنهم
 * لا يستخدمونها إلا إذا طلبتُها صراحةً». فيضع هذا الهوك في سياق كلّ جلسة فهرساً بكلّ مهارةٍ في
 * `.claude/skills/` (الاسم والوصف المختصر) مع القاعدة: طابِق المهمّة بالمهارة واقرأها قبل العمل.
 * لا يكتب شيئاً، ولا يُفشل الجلسة أبداً.
 */
const fs = require('fs');
const path = require('path');

const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const dir = path.join(root, '.claude', 'skills');

function frontmatter(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  if (!m) return {};
  const out = {};
  const lines = m[1].split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const kv = /^(name|description):\s*(.*)$/.exec(lines[i]);
    if (!kv) continue;
    let v = kv[2].trim();
    // وصفٌ مطويّ (‎>‎ أو ‎|‎ أو سطرٌ فارغ): تُضمّ الأسطر المزاحة بعده.
    // وكذلك القيمةُ العاديّة الممتدّة على أسطرٍ مزاحة (YAML plain multi-line).
    if (v === '>' || v === '|' || v === '>-' || v === '|-') v = '';
    const parts = v ? [v] : [];
    while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1])) parts.push(lines[++i].trim());
    v = parts.join(' ');
    out[kv[1]] = v.replace(/^["']|["']$/g, '');
  }
  return out;
}

let rows = [];
try {
  for (const d of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!d.isDirectory()) continue;
    let text;
    try {
      text = fs.readFileSync(path.join(dir, d.name, 'SKILL.md'), 'utf8');
    } catch {
      continue;
    }
    const fm = frontmatter(text);
    const desc = (fm.description || '').replace(/\s+/g, ' ').slice(0, 160);
    rows.push(`- ${fm.name || d.name}: ${desc}`);
  }
} catch {
  process.exit(0);
}
if (!rows.length) process.exit(0);
rows.sort();

process.stdout.write(
  [
    '📚 مهارات هذا المستودع (أمر المالك 2026-11-01 — إلزاميّ بلا طلبٍ صريح):',
    'قبل البدء في أيّ مهمّة طابِقها بالقائمة أدناه، واقرأ SKILL.md لكلّ مهارةٍ تنطبق (`.claude/skills/<الاسم>/SKILL.md`) واتّبعها.',
    'وكلُّ تكليفٍ لوكيلٍ فرعيّ يسمّي المهارات المنطبقة ويأمره بقراءتها. وفي التقرير اذكر بسطرٍ أيَّ مهارةٍ استعملت.',
    ...rows,
    '',
  ].join('\n'),
);
