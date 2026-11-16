import DocsLayout from '../components/DocsLayout';

const toc = [
  { id: 'overview',      label: 'Overview' },
  { id: 'before-after',  label: 'Before vs After Engine' },
  { id: 'suites',        label: 'Benchmark Suites' },
  { id: 'running',       label: 'Running Benchmarks' },
  { id: 'providers',     label: 'Provider Comparison' },
  { id: 'regression',    label: 'Regression Detection' },
  { id: 'api',           label: 'API Access' },
];

const suites = [
  {
    name: 'baseline',
    label: 'Baseline (Raw LLM)',
    color: '#3b82f6',
    badge: 'Before Luna Engine',
    metrics: ['TTFT p50 / p95 / p99', 'Sustained tok/s', 'Cold vs warm latency', 'End-to-end latency'],
    description:
      'Direct call to the configured LLM provider with no system prompt, no memory, and no Luna pipeline overhead. ' +
      'This is the theoretical maximum speed — the raw inference floor for your hardware and model. ' +
      'Every other suite adds on top of this.',
  },
  {
    name: 'engine',
    label: 'Luna Engine (Full Pipeline)',
    color: '#8b5cf6',
    badge: 'After Luna Engine',
    metrics: ['Engine TTFT (retrieval + LLM)', 'Memory retrieval cost', 'Context injection overhead', 'tok/s (decode unchanged)'],
    description:
      'Full Luna pipeline: ChromaDB memory retrieval → system prompt construction with user context → LLM call. ' +
      'Compares directly against baseline. The delta shows what the engine costs in latency, ' +
      'and what it buys in contextual quality.',
  },
  {
    name: 'memory',
    label: 'Memory System',
    color: '#06b6d4',
    badge: 'Retrieval quality',
    metrics: ['Retrieval latency p50 / p95', 'Hit rate (facts returned)', 'Category precision', 'Scaling as DB grows'],
    description:
      'Runs 6 semantic probe queries against the ChromaDB vector store. ' +
      'Measures how fast relevant facts surface, whether the right category is returned, ' +
      'and whether the memory system degrades as the fact database grows. ' +
      'Hit-rate metrics require at least 10 stored facts.',
  },
  {
    name: 'tools',
    label: 'Tool Execution',
    color: '#10b981',
    badge: 'Reliability',
    metrics: ['Per-tool success rate', 'Latency p50 / p95', 'Overall success rate', 'Error classification'],
    description:
      'Executes a set of safe, read-only tools (workspace list, web search) multiple times ' +
      'and measures success rate and latency. Only tools that cannot modify state are run — ' +
      'destructive operations are excluded from automated benchmarks.',
  },
  {
    name: 'agent',
    label: 'Agent Routing',
    color: '#f59e0b',
    badge: 'Agentic accuracy',
    metrics: ['Tool selection accuracy', 'Planning latency p50 / p95', 'Per-request pass rate', 'Hallucinated tool calls'],
    description:
      'Presents the LLM with 6 user requests and asks it to select the correct tool from the real TOOL_REGISTRY. ' +
      'Accuracy measures how reliably the model picks the right tool on the first attempt. ' +
      'Planning latency is the time to produce a valid JSON tool selection.',
  },
  {
    name: 'voice',
    label: 'Voice Pipeline',
    color: '#ec4899',
    badge: 'Conversational feel',
    metrics: ['TTS latency p50 / p95', 'Audio KB per sample', 'STT engine availability', 'Chars-per-second throughput'],
    description:
      'Measures text-to-speech generation latency via edge-tts across 4 sample sentences of varying length. ' +
      'Also checks whether a speech-to-text engine (vosk or faster-whisper) is installed. ' +
      'Full STT benchmarking requires a live microphone and is run separately.',
  },
  {
    name: 'quality',
    label: 'Instruction Quality',
    color: '#a78bfa',
    badge: 'Output correctness',
    metrics: ['Overall instruction score', 'Exact-output compliance', 'Persona consistency', 'Long-context retention', 'Negation following', 'JSON format compliance'],
    description:
      '8-probe battery testing whether the model follows precise instructions: exact word counts, ' +
      'structured output formats, persona identity, basic factuality, negation constraints, ' +
      'JSON schemas, and whether it retains information from earlier in the same prompt.',
  },
  {
    name: 'system',
    label: 'System Resources',
    color: '#22d3ee',
    badge: 'Hardware footprint',
    metrics: ['Idle RAM (MB)', 'Peak RAM during inference', 'RAM delta', 'CPU % at idle vs peak', 'VRAM idle + peak (NVIDIA)', 'Average CPU during generation'],
    description:
      'Uses psutil to sample RAM and CPU every 250 ms while running a long-form inference task. ' +
      'On NVIDIA systems, also queries VRAM via nvidia-smi. ' +
      'The delta columns show exactly how much resource Luna consumes during active generation ' +
      'versus when idle — critical for sizing self-hosted deployments.',
  },
];

function SuiteCard({ suite }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: `1px solid ${suite.color}33`,
      borderRadius: 10,
      padding: '20px 24px',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <span style={{
          fontFamily: 'monospace',
          fontSize: 13,
          fontWeight: 700,
          color: suite.color,
          background: `${suite.color}18`,
          padding: '2px 8px',
          borderRadius: 4,
        }}>{suite.name}</span>
        <span style={{ fontWeight: 700, fontSize: 15 }}>{suite.label}</span>
        <span style={{
          marginLeft: 'auto',
          fontSize: 11,
          color: suite.color,
          background: `${suite.color}15`,
          padding: '2px 8px',
          borderRadius: 12,
          border: `1px solid ${suite.color}30`,
        }}>{suite.badge}</span>
      </div>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12, lineHeight: 1.6 }}>
        {suite.description}
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {suite.metrics.map(m => (
          <span key={m} style={{
            fontSize: 11,
            color: 'var(--text-secondary)',
            background: 'rgba(255,255,255,0.04)',
            padding: '2px 8px',
            borderRadius: 4,
            border: '1px solid rgba(255,255,255,0.08)',
          }}>{m}</span>
        ))}
      </div>
    </div>
  );
}

function CodeBlock({ children }) {
  return (
    <pre style={{
      background: 'rgba(0,0,0,0.35)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 8,
      padding: '16px 20px',
      overflowX: 'auto',
      fontSize: 13,
      lineHeight: 1.6,
      color: '#c9d1d9',
      margin: '12px 0',
    }}><code>{children}</code></pre>
  );
}

function Callout({ color = '#3b82f6', children }) {
  return (
    <div style={{
      background: `${color}10`,
      border: `1px solid ${color}30`,
      borderLeft: `3px solid ${color}`,
      borderRadius: '0 8px 8px 0',
      padding: '12px 16px',
      margin: '16px 0',
      fontSize: 14,
      lineHeight: 1.6,
      color: 'var(--text-secondary)',
    }}>{children}</div>
  );
}

function DeltaTable() {
  const rows = [
    { metric: 'TTFT p50', base: 'provider speed', engine: 'base + retrieval', delta: '+5–30 ms', note: 'ChromaDB lookup cost' },
    { metric: 'TTFT p95', base: 'provider speed', engine: 'base + retrieval', delta: '+10–50 ms', note: 'worst-case retrieval' },
    { metric: 'Sustained tok/s', base: 'model max', engine: 'model max', delta: '≈ 0', note: 'decode is unaffected by context' },
    { metric: 'Memory retrieval', base: '—', engine: 'measured separately', delta: 'counted in overhead', note: 'ChromaDB vector search' },
    { metric: 'Context quality', base: 'plain prompt', engine: 'memory-augmented', delta: '✓ improved', note: 'user history injected' },
    { metric: 'Tool access', base: '—', engine: 'full registry', delta: '✓ enabled', note: 'requires engine' },
    { metric: 'Persona', base: 'none', engine: 'L.U.N.A. identity', delta: '✓ consistent', note: 'system prompt injection' },
  ];
  return (
    <div style={{ overflowX: 'auto', margin: '16px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            {['Metric', 'Raw LLM (Baseline)', 'Luna Engine', 'Delta', 'Notes'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '8px 12px', fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{r.metric}</td>
              <td style={{ padding: '8px 12px', color: '#60a5fa' }}>{r.base}</td>
              <td style={{ padding: '8px 12px', color: '#a78bfa' }}>{r.engine}</td>
              <td style={{ padding: '8px 12px', color: r.delta.startsWith('✓') ? '#34d399' : r.delta === '≈ 0' ? '#9ca3af' : '#fbbf24' }}>{r.delta}</td>
              <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: 11 }}>{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProviderTable() {
  const providers = [
    { name: 'Ollama (local)', ttft: '300–600 ms', tps: '20–80', quality: '★★★★', note: 'depends on GPU/model size' },
    { name: 'Groq',           ttft: '100–300 ms', tps: '200–300', quality: '★★★★★', note: '~300 tok/s cloud inference' },
    { name: 'Anthropic',      ttft: '200–500 ms', tps: '100–200', quality: '★★★★★', note: 'Claude models, SOTA quality' },
    { name: 'Google Gemini',  ttft: '200–400 ms', tps: '100–200', quality: '★★★★★', note: 'multimodal, long context' },
    { name: 'OpenAI',         ttft: '200–500 ms', tps: '50–100',  quality: '★★★★★', note: 'GPT-4o and variants' },
    { name: 'Mistral',        ttft: '200–400 ms', tps: '100–200', quality: '★★★★', note: 'fast EU-based inference' },
    { name: 'Cohere',         ttft: '200–500 ms', tps: '80–150',  quality: '★★★★', note: 'RAG-optimised Command-R' },
  ];
  return (
    <div style={{ overflowX: 'auto', margin: '16px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            {['Provider', 'TTFT (typical)', 'tok/s (typical)', 'Quality', 'Notes'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {providers.map((p, i) => (
            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
              <td style={{ padding: '8px 12px', fontWeight: 600 }}>{p.name}</td>
              <td style={{ padding: '8px 12px', color: '#60a5fa' }}>{p.ttft}</td>
              <td style={{ padding: '8px 12px', color: '#34d399' }}>{p.tps}</td>
              <td style={{ padding: '8px 12px', color: '#fbbf24', fontFamily: 'monospace' }}>{p.quality}</td>
              <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontSize: 11 }}>{p.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BenchmarksPage() {
  return (
    <DocsLayout
      title="Benchmarks — Luna"
      description="Comprehensive Luna benchmark suite: 8 suites measuring inference speed, memory retrieval, tool routing accuracy, voice latency, instruction quality, and system resources — before and after the Luna engine."
      toc={toc}
    >
      <h1>Benchmarks</h1>
      <p style={{ fontSize: 16, lineHeight: 1.7, color: 'var(--text-secondary)', marginBottom: 24 }}>
        Luna's benchmark suite measures eight dimensions of AI engine performance — from raw inference speed
        to instruction quality to hardware footprint. The key output is a <strong>Before vs After Luna Engine</strong> comparison
        that shows exactly what the pipeline costs in latency and what it buys in contextual quality.
      </p>

      <img
        src="/images/benchmark-overview.svg"
        alt="Luna benchmark suite overview"
        style={{ width: '100%', borderRadius: 12, marginBottom: 32 }}
      />

      <h2 id="overview">Overview</h2>
      <p>
        Most AI benchmarks only measure tok/s and TTFT. Real AI engine deployments care about much more:
        how fast memory surfaces relevant context, whether the agent picks the right tool, whether the model
        follows precise instructions, and what the RAM footprint looks like on a shared server.
      </p>
      <p>
        Luna's benchmark runner measures all of this in a single command, saves results to the database
        for trend tracking, and emits a regression warning when any metric worsens by more than 25%.
      </p>

      <h2 id="before-after">Before vs After Luna Engine</h2>
      <p>
        The most important benchmark dimension is the cost/benefit of Luna's pipeline.
        Every call goes through two measurable phases:
      </p>
      <ol>
        <li><strong>Baseline (raw LLM)</strong> — direct provider API call with no system prompt and no memory lookup. This is the theoretical speed ceiling.</li>
        <li><strong>Luna Engine</strong> — the same call after ChromaDB retrieval + context injection + system prompt construction. This is what users actually experience.</li>
      </ol>
      <DeltaTable />
      <Callout color="#8b5cf6">
        The pipeline overhead is typically <strong>+5–30 ms</strong> — dominated by the ChromaDB vector search.
        Token generation speed (tok/s) is unaffected because it depends only on the model and hardware,
        not on how long the system prompt is.
      </Callout>

      <h2 id="suites">Benchmark Suites</h2>
      <p>Eight suites, each targeting a different layer of the AI engine stack:</p>
      {suites.map(s => <SuiteCard key={s.name} suite={s} />)}

      <h2 id="running">Running Benchmarks</h2>

      <h3>Full suite (all 8 benchmarks)</h3>
      <CodeBlock>{`python scripts/run_benchmark.py`}</CodeBlock>

      <h3>Before vs after comparison only</h3>
      <CodeBlock>{`python scripts/run_benchmark.py --suite baseline,engine`}</CodeBlock>

      <h3>Specific suites</h3>
      <CodeBlock>{`python scripts/run_benchmark.py --suite quality,agent,voice
python scripts/run_benchmark.py --suite system --runs 2`}</CodeBlock>

      <h3>More statistical stability (more runs)</h3>
      <CodeBlock>{`python scripts/run_benchmark.py --runs 5        # 5 warm runs per probe
python scripts/run_benchmark.py --suite llm --runs 10`}</CodeBlock>

      <h3>JSON output for dashboards</h3>
      <CodeBlock>{`python scripts/run_benchmark.py --json results/bench.json`}</CodeBlock>

      <p>
        Results are automatically saved to the <code>benchmark_results</code> table and can be queried
        via <code>GET /api/observe/benchmark</code>.
      </p>

      <h2 id="providers">Provider Comparison</h2>
      <p>
        Run the same suite with different providers using <code>--provider</code> to compare raw speed.
        The baseline suite is the cleanest way to compare providers because it strips all Luna overhead.
      </p>
      <CodeBlock>{`# Baseline: Ollama local
python scripts/run_benchmark.py --suite baseline --provider ollama

# Compare: Groq cloud (~300 tok/s)
python scripts/run_benchmark.py --suite baseline --provider groq \\
  --model llama-3.3-70b-versatile

# Compare: Anthropic
python scripts/run_benchmark.py --suite baseline --provider anthropic \\
  --model claude-sonnet-4-5

# Compare: Google Gemini
python scripts/run_benchmark.py --suite baseline --provider google \\
  --model gemini-2.0-flash`}</CodeBlock>

      <ProviderTable />

      <Callout color="#3b82f6">
        Typical ranges above are indicative — real numbers depend on your network, server load,
        and model size. Run the benchmark on your hardware for authoritative results.
      </Callout>

      <h2 id="regression">Regression Detection</h2>
      <p>
        Every benchmark run is saved to the database. On subsequent runs, the runner compares the
        current results against the previous run and flags any metric that worsened by more than 25%.
      </p>
      <CodeBlock>{`# Regressions vs previous run
  [baseline] TTFT mean regressed +28%  (320.0 → 410.0)
  [quality]  quality score regressed -30%  (0.87 → 0.62)`}</CodeBlock>
      <p>
        Regressions appear at the top of the Markdown report and in the console summary.
        The threshold is configurable in <code>scripts/run_benchmark.py</code> via <code>REGRESSION_THRESHOLD</code>.
      </p>

      <h2 id="api">API Access</h2>
      <p>Benchmark history is accessible via the observability API:</p>
      <CodeBlock>{`# Latest result per suite
GET /api/observe/benchmark

# Suite history (last 20 runs)
GET /api/observe/benchmark?suite=baseline&limit=20

# Run a benchmark from the API (admin only)
POST /api/admin/benchmark/run
Authorization: Bearer <jwt_secret>
{ "suite": "baseline,engine", "runs": 3 }`}</CodeBlock>
    </DocsLayout>
  );
}
