import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'facts',        label: 'Facts' },
  { id: 'embeddings',   label: 'Embeddings & search' },
  { id: 'personality',  label: 'Personality engine' },
  { id: 'compaction',   label: 'Conversation compaction' },
  { id: 'api',          label: 'Memory API' },
  { id: 'privacy',      label: 'Privacy' },
];

export default function Memory() {
  return (
    <DocsLayout
      title="Memory"
      description="How Luna stores and retrieves facts, runs semantic search with ChromaDB, maintains personality state, and compacts conversations."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna's memory is a three-tier system that gives it persistent, searchable context across sessions.
          Unlike a stateless chatbot that forgets everything when you close the window, Luna builds a
          personal model of you over time — your preferences, habits, projects, and personality.
        </p>
        <p>Everything is stored locally. No external service is involved.</p>

        <table>
          <thead><tr><th>Tier</th><th>Storage</th><th>Purpose</th></tr></thead>
          <tbody>
            <tr><td>Facts</td><td>SQLite (<code>data/luna.db</code>)</td><td>Structured facts extracted from conversations.</td></tr>
            <tr><td>Embeddings</td><td>ChromaDB (<code>data/chroma/</code>)</td><td>Vector representations for semantic similarity search.</td></tr>
            <tr><td>Personality</td><td>SQLite</td><td>Floating-point state vector for response tone adaptation.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="facts">Facts</h2>
        <p>
          A <em>fact</em> is a discrete piece of information about you that Luna has extracted or been told.
          Facts are rows in the <code>Fact</code> table with the following structure:
        </p>

        <table>
          <thead><tr><th>Column</th><th>Type</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>id</code></td><td>UUID</td><td>Unique identifier.</td></tr>
            <tr><td><code>content</code></td><td>text</td><td>The fact itself, e.g. <em>"user prefers dark mode interfaces"</em>.</td></tr>
            <tr><td><code>source_conversation</code></td><td>UUID</td><td>Which conversation produced this fact.</td></tr>
            <tr><td><code>confidence</code></td><td>float 0–1</td><td>Extraction confidence. Low-confidence facts are pruned over time.</td></tr>
            <tr><td><code>created_at</code></td><td>datetime</td><td>When the fact was first recorded.</td></tr>
            <tr><td><code>last_accessed</code></td><td>datetime</td><td>Updated when the fact is retrieved for context. Used for pruning.</td></tr>
          </tbody>
        </table>

        <h3>How facts are extracted</h3>
        <p>
          The <code>memory_maintenance</code> background process runs every 5 minutes. It scans recent
          conversations that haven't been processed yet, sends them to <code>backend/services/fact_extractor.py</code>,
          and stores the results. The extractor uses a lightweight LLM prompt to identify facts.
        </p>

        <p>You can also tell Luna a fact directly:</p>
        <pre><code>{`"Remember that I'm lactose intolerant."
"My meeting with the design team is every Tuesday at 2pm."`}</code></pre>

        <p>Luna will store these as high-confidence facts immediately via the memory route.</p>

        <h3>Viewing and managing facts</h3>
        <p>Open the <strong>Memory</strong> view in the sidebar. You can see all stored facts, their
        confidence scores, and delete any you don't want. You can also add facts manually.</p>
      </section>

      <section>
        <h2 id="embeddings">Embeddings and semantic search</h2>
        <p>
          Every fact is embedded using <code>nomic-embed-text</code> via Ollama and stored in a ChromaDB
          collection at <code>data/chroma/</code>. The embeddings are 768-dimensional vectors.
        </p>

        <h3>Context retrieval</h3>
        <p>
          When a new message arrives, Luna embeds the user's query and runs a cosine similarity search
          against the fact collection. The top-k most relevant facts are injected into the system prompt —
          not just the most recent facts, but the most semantically related ones.
        </p>

        <p>For example, if you mention <em>"what should I have for dinner?"</em> and Luna stored the fact
        <em>"user is vegetarian and doesn't like spicy food"</em> six months ago, that fact surfaces even
        though it was never recently accessed.</p>

        <Callout type="info" title="Cold start">
          <p>On first run, ChromaDB will be empty. Luna will have no memory of previous conversations.
          After a few sessions the memory fills in and context quality improves noticeably.</p>
        </Callout>

        <h3>Rebuilding the index</h3>
        <p>If the ChromaDB collection becomes corrupted, delete <code>data/chroma/</code> and restart Luna.
        The collection rebuilds from the SQLite facts on next startup.</p>
      </section>

      <section>
        <h2 id="personality">Personality engine</h2>
        <p>
          <code>backend/services/personality.py</code> maintains a state vector that adapts Luna's
          response tone in real time. The vector has five dimensions:
        </p>

        <table>
          <thead><tr><th>Dimension</th><th>Range</th><th>Effect on responses</th></tr></thead>
          <tbody>
            <tr><td><code>mood</code></td><td>-1.0 to 1.0</td><td>Negative mood → more empathetic, careful tone. Positive → warmer, more playful.</td></tr>
            <tr><td><code>energy</code></td><td>0.0 to 1.0</td><td>Low energy → concise responses. High energy → more expansive answers.</td></tr>
            <tr><td><code>formality</code></td><td>0.0 to 1.0</td><td>Low formality → casual language. High formality → professional tone.</td></tr>
            <tr><td><code>humor</code></td><td>0.0 to 1.0</td><td>Controls how often Luna makes jokes or playful observations.</td></tr>
            <tr><td><code>emotional_support</code></td><td>0.0 to 1.0</td><td>High → Luna prioritises empathy over information delivery.</td></tr>
          </tbody>
        </table>

        <p>These values drift based on conversation sentiment analysis and voice emotion detection. They
        are included in every system prompt so the LLM can adapt its style accordingly.</p>

        <p>You can view and manually adjust personality state in the <strong>Memory → Personality</strong>
        tab in the sidebar.</p>
      </section>

      <section>
        <h2 id="compaction">Conversation compaction</h2>
        <p>
          Long conversations would eventually overflow the LLM's context window. The
          <code>memory_maintenance</code> process compacts conversations older than a configurable
          threshold into compressed summaries.
        </p>

        <p>Compaction works in two stages:</p>
        <ol>
          <li>An LLM prompt summarises the conversation into bullet points of key decisions, facts mentioned, and emotional tone.</li>
          <li>The summary replaces the full conversation in context retrieval. The original messages are
          archived in SQLite but no longer included in prompts.</li>
        </ol>

        <Callout type="note" title="Compaction threshold">
          <p>By default, conversations longer than 40 messages trigger compaction. This is configurable
          in <code>backend/processes/memory_maintenance/</code>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="api">Memory API</h2>
        <p>The memory system is accessible via REST for scripting or integration:</p>

        <CodeFile label="Examples">
          <pre><code>{`# List all facts
GET /api/memory/facts

# Add a fact manually
POST /api/memory/facts
{"content": "user prefers concise answers", "confidence": 0.9}

# Delete a fact
DELETE /api/memory/facts/{id}

# Semantic search
POST /api/memory/search
{"query": "dietary preferences", "limit": 5}

# Get personality state
GET /api/memory/personality

# Update a personality dimension
PUT /api/memory/personality
{"humor": 0.8, "formality": 0.2}`}</code></pre>
        </CodeFile>

        <p>Business variant routes require <code>Authorization: Bearer &lt;user-jwt&gt;</code>.</p>
      </section>

      <section>
        <h2 id="privacy">Privacy</h2>
        <ul>
          <li>All facts, embeddings, and personality state are stored in <code>data/</code> on your machine.</li>
          <li><code>data/</code> is gitignored — it is never committed to version control.</li>
          <li>No memory data is sent to Ollama during embedding — only the text of the fact.</li>
          <li>If you use an OpenAI-compatible embedding provider, that provider receives the fact text for embedding. Choose a local provider if this concerns you.</li>
          <li>You can delete all memory at any time by removing <code>data/luna.db</code> and <code>data/chroma/</code>.</li>
        </ul>
      </section>

      <NextSteps items={[
        { href: '/architecture', label: 'Deep dive', title: 'Architecture',    desc: 'How memory integrates with the message lifecycle and context assembly.' },
        { href: '/agent',        label: 'Feature',   title: 'Agent & Skills',  desc: 'Extend Luna with custom skills that can interact with the memory system.' },
        { href: '/api',          label: 'Platform',  title: 'API reference',   desc: 'Full memory API endpoint documentation.' },
      ]} />
    </DocsLayout>
  );
}
