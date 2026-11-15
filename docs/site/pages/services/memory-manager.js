import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',    label: 'Overview' },
  { id: 'init',        label: 'Instantiation' },
  { id: 'store-fact',  label: 'store_fact()' },
  { id: 'retrieve',    label: 'retrieve_relevant()' },
  { id: 'core-facts',  label: 'get_core_facts()' },
  { id: 'context',     label: 'get_conversation_context()' },
  { id: 'compact',     label: 'compact_facts()' },
  { id: 'summaries',   label: 'Conversation summaries' },
  { id: 'contradiction', label: 'Contradiction detection' },
  { id: 'memory-types', label: 'Memory types' },
];

export default function MemoryManagerService() {
  return (
    <DocsLayout
      title="Memory Manager"
      description="Long-term fact storage, ChromaDB semantic search, conversation summarisation, and background contradiction detection."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>MemoryManager</code> is the central memory layer. It combines:
        </p>
        <ul>
          <li>A <strong>SQLite facts table</strong> — structured, queryable, persistent facts extracted from conversations.</li>
          <li>A <strong>ChromaDB collection</strong> (<code>luna_facts</code>) — embedding vectors for semantic similarity search.</li>
          <li>A <strong>conversation history</strong> buffer — the last N messages injected as context.</li>
        </ul>
        <p>One instance is created per request and shares the same SQLAlchemy session as the router.</p>

        <table>
          <thead><tr><th>File</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>memory_manager/manager.py</code></td><td>Full <code>MemoryManager</code> class — single module (tight self.db coupling).</td></tr>
            <tr><td><code>memory_manager/__init__.py</code></td><td>Re-exports <code>MemoryManager</code>.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="init">Instantiation</h2>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.memory_manager import MemoryManager
from backend.models.database import SessionLocal

db = SessionLocal()
mm = MemoryManager(db)

# ... use mm ...

db.close()`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          In FastAPI routes, use <code>db: Session = Depends(get_db)</code> — the session is
          managed by the dependency injector. Never share a MemoryManager instance across requests.
        </Callout>
      </section>

      <section>
        <h2 id="store-fact">store_fact()</h2>
        <p>Persists a fact to SQLite and embeds it into ChromaDB.</p>
        <CodeFile label="signature">
          <pre><code>{`async def store_fact(
    content: str,
    category: str,           # "preference" | "goal" | "behavior" | "identity" | "context" | ...
    memory_type: str = "long",  # "long" | "short"
    importance: float = 0.7,    # 0.0 – 1.0
    confidence: float = 0.85,
    source: str = "conversation",
    expires_at: datetime | None = None,
) -> int  # returns the new fact's database ID`}</code></pre>
        </CodeFile>

        <h3>Categories</h3>
        <table>
          <thead><tr><th>Category</th><th>Example</th></tr></thead>
          <tbody>
            <tr><td><code>preference</code></td><td>"User prefers dark mode"</td></tr>
            <tr><td><code>goal</code></td><td>"User wants to learn Rust this year"</td></tr>
            <tr><td><code>behavior</code></td><td>"User is frequently active late at night"</td></tr>
            <tr><td><code>identity</code></td><td>"User is a backend engineer at a startup"</td></tr>
            <tr><td><code>context</code></td><td>"User is working on a FastAPI project called Luna"</td></tr>
            <tr><td><code>routine</code></td><td>"User starts work at 9 AM on weekdays"</td></tr>
          </tbody>
        </table>

        <h3>Usage</h3>
        <CodeFile label="example.py">
          <pre><code>{`# Store a long-term preference
fact_id = await mm.store_fact(
    "User strongly prefers Python over JavaScript",
    category="preference",
    importance=0.9,
)

# Store a short-lived context fact with expiry
from datetime import datetime, timedelta
await mm.store_fact(
    "User is currently debugging a memory leak",
    category="context",
    memory_type="short",
    expires_at=datetime.utcnow() + timedelta(hours=2),
)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="retrieve">retrieve_relevant()</h2>
        <p>
          Returns the most semantically relevant active facts for a query using ChromaDB
          cosine similarity, with a SQLite text-search fallback if embeddings are unavailable.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def retrieve_relevant(
    query: str,
    limit: int = 6,
) -> list[Fact]  # SQLAlchemy Fact ORM objects`}</code></pre>
        </CodeFile>

        <CodeFile label="example.py">
          <pre><code>{`facts = await mm.retrieve_relevant("what programming languages does the user know?")
for fact in facts:
    print(f"[{fact.category}] {fact.content}  (confidence={fact.confidence:.2f})")`}</code></pre>
        </CodeFile>

        <Callout type="note">
          The retrieval count is configurable via <code>MEMORY_RETRIEVAL_COUNT</code> in <code>.env</code> (default: 6).
        </Callout>
      </section>

      <section>
        <h2 id="core-facts">get_core_facts()</h2>
        <p>
          Returns high-importance, high-confidence facts that are always injected into the
          system prompt regardless of query relevance. These are the "always know" facts —
          things like the user's name, profession, and key goals.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def get_core_facts(limit: int = 10) -> list[Fact]`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`core = mm.get_core_facts()
for f in core:
    print(f.content)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="context">get_conversation_context()</h2>
        <p>
          Builds the full context string that is injected before the LLM system prompt.
          Combines core facts, relevant facts, and recent conversation summary.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def get_conversation_context(
    query: str,
    conversation_id: int | None = None,
) -> str`}</code></pre>
        </CodeFile>

        <h3>What it includes</h3>
        <ol>
          <li>Core facts (always-on, high importance).</li>
          <li>Semantically retrieved facts for the current query.</li>
          <li>The most recent conversation summary (if one exists).</li>
        </ol>

        <CodeFile label="example.py">
          <pre><code>{`context = await mm.get_conversation_context(
    query=user_message,
    conversation_id=current_conversation_id,
)
# Prepend to system prompt
full_system = context + "\\n\\n" + base_system_prompt`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="compact">compact_facts()</h2>
        <p>
          Removes duplicate and contradicted facts using an LLM pass. Runs daily at 3 AM
          via the scheduler, but can be called manually.
        </p>
        <CodeFile label="signature">
          <pre><code>{`async def compact_facts() -> int  # returns number of facts removed`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`removed = await mm.compact_facts()
print(f"Removed {removed} redundant facts")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="summaries">Conversation summaries</h2>
        <p>
          After every N messages, the chat pipeline stores a compressed summary of the
          conversation as a memory record. This allows Luna to maintain context across
          very long sessions without exceeding the LLM's context window.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`# Store a summary manually
await mm.store_conversation_summary(
    conversation_id=42,
    summary="User and Luna discussed the Rust borrow checker for 20 minutes.",
)

# Retrieve recent conversation context
recent = mm.get_recent_conversation(limit=6)
for msg in recent:
    print(f"{msg.role}: {msg.content[:80]}")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="contradiction">Contradiction detection</h2>
        <p>
          When a new fact is stored, a background task calls the LLM to check whether it
          contradicts any existing fact in the same category. If a contradiction is found,
          the older fact is deactivated and a <code>ContradictionNote</code> record is created.
        </p>
        <p>This happens asynchronously — <code>store_fact()</code> returns immediately
          and the contradiction check runs in the background.
        </p>
      </section>

      <section>
        <h2 id="memory-types">Memory types</h2>
        <table>
          <thead><tr><th>Type</th><th>Lifespan</th><th>Use for</th></tr></thead>
          <tbody>
            <tr><td><code>long</code></td><td>Permanent (until compacted)</td><td>Preferences, goals, identity facts.</td></tr>
            <tr><td><code>short</code></td><td>Until <code>expires_at</code></td><td>Current task context, temporary state.</td></tr>
          </tbody>
        </table>
        <p>
          Short-term facts are automatically pruned by <code>_expire_stale_facts()</code>
          which runs every time a new fact is stored.
        </p>
      </section>

      <NextSteps items={[
        { href: '/services/memory-graph', label: 'Service', title: 'Memory Graph', desc: 'Graph traversal and episodic memory on top of facts.' },
        { href: '/services/personality',  label: 'Service', title: 'Personality Engine', desc: 'How facts feed into personality prompt building.' },
        { href: '/memory',               label: 'Feature', title: 'Memory Overview', desc: 'High-level explanation of Luna\'s three-tier memory system.' },
      ]} />
    </DocsLayout>
  );
}
