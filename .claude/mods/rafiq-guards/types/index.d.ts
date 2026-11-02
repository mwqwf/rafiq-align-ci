// عقد حالة المود: سجلُّ ما ردّه الحراس في الجلسة لتعرضه اللوحة.
export type Denial = { at: string; tool: string; guard: string; reason: string }

declare module 'claude-code' {
  interface PluginState {
    'rafiq-guards': { denials: Shaped<Denial[]> }
  }
}
