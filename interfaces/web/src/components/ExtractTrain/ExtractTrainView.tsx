import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FlaskConical, Play, Plus, Trash2, Loader2, CheckCircle } from 'lucide-react'
import { authHeaders } from '../../api/client'

interface ExtractionPair {
  id: number
  conversation: string
  chosen: string
  rejected: string[]
  note?: string
  timestamp: string
}

const TYPE_COLOR: Record<string, string> = {
  persistent: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  short:      'bg-amber-500/15 text-amber-300 border-amber-500/30',
  long:       'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
}

function parseResult(raw: string): { type: string; category: string; content: string }[] {
  try {
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr.map((f: any) => ({
      type: f.memory_type ?? 'long',
      category: f.category ?? '?',
      content: f.content ?? '',
    }))
  } catch {
    return []
  }
}

export function ExtractTrainView() {
  const [pairs, setPairs] = useState<ExtractionPair[]>([])
  const [conversation, setConversation] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)
  const [chosen, setChosen] = useState('[]')
  const [note, setNote] = useState('')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch('/api/train/pairs?mode=extraction', { headers: authHeaders() })
      .then(r => r.json())
      .then(d => setPairs(d.pairs ?? []))
      .catch(() => {})
  }, [])

  const runTest = async () => {
    if (!conversation.trim()) return
    setTesting(true)
    setTestResult(null)
    try {
      const r = await fetch('/api/train/test-extraction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ conversation }),
      })
      const d = await r.json()
      setTestResult(d.result ?? '[]')
      setChosen(d.result ?? '[]')
    } finally {
      setTesting(false)
    }
  }

  const savePair = async () => {
    if (!conversation.trim()) return
    setSaving(true)
    try {
      const r = await fetch('/api/train/save-extraction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ conversation, chosen, note }),
      })
      const d = await r.json()
      if (d.ok) {
        setPairs(prev => [{
          id: d.id,
          conversation,
          chosen,
          rejected: [],
          note,
          timestamp: new Date().toISOString(),
        }, ...prev])
        setConversation('')
        setTestResult(null)
        setChosen('[]')
        setNote('')
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      }
    } finally {
      setSaving(false)
    }
  }

  const deletePair = async (id: number) => {
    await fetch(`/api/train/pairs/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    setPairs(prev => prev.filter(p => p.id !== id))
  }

  const facts = testResult ? parseResult(testResult) : []

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="flex items-center gap-3 mb-6">
        <FlaskConical size={20} className="text-luna-primary" />
        <h2 className="text-lg font-semibold text-luna-text">Extraction Training</h2>
        <span className="ml-auto text-xs text-luna-dim">{pairs.length} pairs</span>
      </div>

      {/* Test panel */}
      <div className="bg-luna-card border border-luna-border rounded-2xl p-5 mb-6 space-y-4">
        <p className="text-xs text-luna-dim">Paste a conversation, test what Luna would extract, then correct and save.</p>

        <textarea
          value={conversation}
          onChange={e => setConversation(e.target.value)}
          placeholder={"User: I'm eating ramen right now\nLuna: Nice! Big fan?\nUser: yeah always with garlic"}
          rows={5}
          className="w-full bg-luna-surface border border-luna-border rounded-xl px-4 py-3 text-sm text-luna-text placeholder-luna-dim outline-none focus:border-luna-primary/50 resize-none font-mono"
        />

        <div className="flex gap-2">
          <button
            onClick={runTest}
            disabled={testing || !conversation.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-luna-primary/20 hover:bg-luna-primary/30 border border-luna-primary/30 text-luna-accent rounded-xl text-sm transition-all disabled:opacity-40"
          >
            {testing ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            Test extraction
          </button>
        </div>

        {/* Current extraction result */}
        {testResult !== null && (
          <div className="space-y-2">
            <p className="text-[11px] text-luna-dim font-medium">What Luna would store now:</p>
            {facts.length === 0 ? (
              <p className="text-xs text-luna-dim italic">Nothing — correctly extracts nothing.</p>
            ) : (
              <div className="space-y-1.5">
                {facts.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 bg-luna-surface rounded-xl px-3 py-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border flex-shrink-0 ${TYPE_COLOR[f.type] ?? TYPE_COLOR.long}`}>
                      {f.type}
                    </span>
                    <span className="text-[10px] text-luna-dim flex-shrink-0 capitalize">{f.category}</span>
                    <span className="text-xs text-luna-text">{f.content}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Editable chosen output */}
            <p className="text-[11px] text-luna-dim font-medium mt-3">Correct output (edit if needed):</p>
            <textarea
              value={chosen}
              onChange={e => setChosen(e.target.value)}
              rows={4}
              className="w-full bg-luna-surface border border-luna-border rounded-xl px-4 py-3 text-xs text-luna-text outline-none focus:border-luna-primary/50 resize-none font-mono"
            />
            <input
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Note (why this is correct / what to avoid)…"
              className="w-full bg-luna-surface border border-luna-border rounded-xl px-4 py-2 text-xs text-luna-text placeholder-luna-dim outline-none focus:border-luna-primary/50"
            />
            <button
              onClick={savePair}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 rounded-xl text-sm transition-all disabled:opacity-40"
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : saved ? <CheckCircle size={13} /> : <Plus size={13} />}
              {saved ? 'Saved!' : 'Save pair'}
            </button>
          </div>
        )}
      </div>

      {/* Existing pairs */}
      <div className="space-y-3">
        {pairs.map(pair => (
          <motion.div
            key={pair.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-luna-card border border-luna-border rounded-2xl p-4 group"
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <pre className="text-xs text-luna-muted font-mono whitespace-pre-wrap leading-relaxed flex-1">{pair.conversation}</pre>
              <button
                onClick={() => deletePair(pair.id)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:text-red-400 flex-shrink-0"
              >
                <Trash2 size={12} />
              </button>
            </div>

            <div className="space-y-1">
              <p className="text-[10px] text-emerald-400 font-medium">Correct:</p>
              {parseResult(pair.chosen).length === 0 ? (
                <p className="text-[11px] text-luna-dim italic">Extract nothing</p>
              ) : (
                parseResult(pair.chosen).map((f, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${TYPE_COLOR[f.type] ?? TYPE_COLOR.long}`}>
                      {f.type}
                    </span>
                    <span className="text-[10px] text-luna-dim capitalize">{f.category}</span>
                    <span className="text-xs text-luna-text">{f.content}</span>
                  </div>
                ))
              )}
            </div>

            {pair.note && (
              <p className="text-[10px] text-luna-dim mt-2 italic"># {pair.note}</p>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}
