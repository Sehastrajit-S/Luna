import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'init',         label: 'Instantiation' },
  { id: 'link',         label: 'link_facts()' },
  { id: 'related',      label: 'get_related_facts()' },
  { id: 'subgraph',     label: 'get_subgraph()' },
  { id: 'clusters',     label: 'find_clusters()' },
  { id: 'episodes',     label: 'Episodic memory' },
  { id: 'rel-types',    label: 'Relationship types' },
  { id: 'models',       label: 'FactNode & GraphEdge' },
];

export default function MemoryGraphService() {
  return (
    <DocsLayout
      title="Memory Graph"
      description="Graph traversal over the fact store plus ChromaDB-backed episodic memory — links facts with typed edges and stores conversation episodes for long-range recall."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>MemoryGraph</code> sits on top of <code>MemoryManager</code> and adds
          two capabilities the flat fact store doesn't have:
        </p>
        <ul>
          <li>
            <strong>Typed edges</strong> — facts can be linked with relationships like
            <code>CONFIRMS</code>, <code>CONTRADICTS</code>, <code>CAUSED_BY</code>, etc.
            Graph traversal (BFS) lets you retrieve chains of related facts that a pure
            semantic search would miss.
          </li>
          <li>
            <strong>Episodic memory</strong> — whole conversations are compressed into
            episodes with a summary, key facts, and an embedding. Retrieving episodes
            gives Luna cross-session narrative context.
          </li>
        </ul>
        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>memory_graph/constants.py</code></td><td><code>REL_*</code> constants, <code>ALL_REL_TYPES</code> list.</td></tr>
            <tr><td><code>memory_graph/models.py</code></td><td><code>FactNode</code>, <code>GraphEdge</code> dataclasses.</td></tr>
            <tr><td><code>memory_graph/graph.py</code></td><td>Full <code>MemoryGraph</code> class.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="init">Instantiation</h2>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.memory_graph import MemoryGraph
from backend.models.database import SessionLocal

db = SessionLocal()
graph = MemoryGraph(db)

# ... use graph ...

db.close()`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          Use the same SQLAlchemy session for both <code>MemoryManager</code> and
          <code>MemoryGraph</code> within the same request — they share the same
          database and the session tracks uncommitted state.
        </Callout>
      </section>

      <section>
        <h2 id="link">link_facts()</h2>
        <p>
          Creates or updates a typed directed edge between two fact IDs. Upserts —
          calling it twice on the same pair updates the relationship type and confidence.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def link_facts(
    fact_a: int,
    fact_b: int,
    relation: str,          # one of the REL_* constants
    confidence: float = 0.8,
    note: str = "",
) -> None`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.memory_graph import MemoryGraph, REL_UPDATES

graph = MemoryGraph(db)

# fact 42 updates (supersedes) fact 17
graph.link_facts(42, 17, REL_UPDATES, confidence=0.95, note="user corrected their job title")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="related">get_related_facts()</h2>
        <p>
          BFS from a seed fact ID through the <code>fact_relationships</code> table.
          Returns all reachable active <code>FactNode</code> objects up to
          <code>max_depth</code> hops away. Can be filtered to specific relationship
          types.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def get_related_facts(
    fact_id: int,
    max_depth: int = 2,
    rel_types: list[str] | None = None,   # filter by relationship type
) -> list[FactNode]`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.memory_graph import MemoryGraph, REL_CONFIRMS, REL_RELATED

graph = MemoryGraph(db)

# All facts within 2 hops of fact 5
nodes = graph.get_related_facts(5, max_depth=2)

# Only confirmation/related edges
nodes = graph.get_related_facts(5, rel_types=[REL_CONFIRMS, REL_RELATED])
for n in nodes:
    print(f"[{n.category}] {n.content}  (conf={n.confidence})")`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="subgraph">get_subgraph()</h2>
        <p>
          Returns a JSON-serialisable dict of nodes and edges for a set of seed fact IDs.
          Useful for rendering a visual memory graph or for feeding structured context
          to the LLM.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def get_subgraph(
    seed_fact_ids: list[int],
    max_depth: int = 2,
) -> dict  # {"nodes": [...], "edges": [...]}`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`subgraph = graph.get_subgraph([5, 12, 33])
print(subgraph["nodes"][0])
# {"id": 5, "content": "...", "category": "preference", "confidence": 0.9, "importance": 0.8}
print(subgraph["edges"][0])
# {"a": 5, "b": 12, "rel": "RELATED", "conf": 0.75}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="clusters">find_clusters()</h2>
        <p>
          Returns the connected components of the active fact graph using Union-Find.
          Each component is a list of fact IDs. Only components with 2 or more nodes
          are returned.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`clusters = graph.find_clusters()
for cluster in clusters:
    print(f"Cluster of {len(cluster)} facts: {cluster}")`}</code></pre>
        </CodeFile>
        <p>
          Useful for visualisation and for detecting isolated facts that have never
          been connected to anything else.
        </p>
      </section>

      <section>
        <h2 id="episodes">Episodic memory</h2>
        <p>
          Episodic memory stores a compressed summary of each conversation alongside
          the IDs of the key facts extracted from it. Episodes are embedded into
          ChromaDB (<code>luna_episodes</code> collection) for semantic retrieval.
        </p>

        <h3>store_episode()</h3>
        <CodeFile label="signature">
          <pre><code>{`def store_episode(
    conversation_id: int,
    summary: str,
    key_fact_ids: list[int],
    key_entities: list[str],
    embed_fn: Callable[[str], list[float]] | None = None,
) -> None`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.llm import ollama

graph.store_episode(
    conversation_id=42,
    summary="User and Luna discussed the Rust borrow checker for 20 minutes. Key insight: lifetime annotations.",
    key_fact_ids=[5, 12, 33],
    key_entities=["Rust", "borrow checker", "lifetime"],
    embed_fn=lambda text: asyncio.run(ollama.embed(text)),
)
# importance = min(1.0, 0.3 + 3 * 0.07) = 0.51`}</code></pre>
        </CodeFile>

        <h3>retrieve_episodes()</h3>
        <p>
          Returns relevant past episodes ordered by semantic similarity to a query.
          Falls back to importance-ordered SQL retrieval if embeddings aren't available.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def retrieve_episodes(
    query: str,
    limit: int = 5,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> list[dict]  # [{"summary", "conversation_id", "importance", "entities"}]`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`episodes = graph.retrieve_episodes(
    "what did we talk about with Rust?",
    embed_fn=lambda t: asyncio.run(ollama.embed(t)),
)
for ep in episodes:
    print(ep["summary"])`}</code></pre>
        </CodeFile>

        <h3>get_episode_facts()</h3>
        <CodeFile label="example.py">
          <pre><code>{`fact_ids = graph.get_episode_facts(conversation_id=42)
# [5, 12, 33]
# Use with get_subgraph() to pull the full context for an episode
subgraph = graph.get_subgraph(fact_ids)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="rel-types">Relationship types</h2>
        <table>
          <thead><tr><th>Constant</th><th>Value</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr><td><code>REL_CONTRADICTS</code></td><td><code>"CONTRADICTS"</code></td><td>Fact A conflicts with fact B.</td></tr>
            <tr><td><code>REL_CONFIRMS</code></td><td><code>"CONFIRMS"</code></td><td>Fact A reinforces fact B.</td></tr>
            <tr><td><code>REL_UPDATES</code></td><td><code>"UPDATES"</code></td><td>Fact A supersedes fact B (more recent).</td></tr>
            <tr><td><code>REL_RELATED</code></td><td><code>"RELATED"</code></td><td>Topically related, no causal direction.</td></tr>
            <tr><td><code>REL_CAUSED_BY</code></td><td><code>"CAUSED_BY"</code></td><td>Fact A is a consequence of fact B.</td></tr>
            <tr><td><code>REL_PRECEDES</code></td><td><code>"PRECEDES"</code></td><td>Fact A happened before fact B.</td></tr>
            <tr><td><code>REL_PART_OF</code></td><td><code>"PART_OF"</code></td><td>Fact A is a component of fact B.</td></tr>
          </tbody>
        </table>
        <CodeFile label="import">
          <pre><code>{`from backend.services.memory_graph import (
    REL_CONTRADICTS, REL_CONFIRMS, REL_UPDATES,
    REL_RELATED, REL_CAUSED_BY, REL_PRECEDES, REL_PART_OF,
    ALL_REL_TYPES,   # list of all seven strings
)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="models">FactNode and GraphEdge</h2>
        <CodeFile label="memory_graph/models.py">
          <pre><code>{`@dataclass
class FactNode:
    id: int
    content: str
    category: str
    confidence: float = 0.8
    importance: float = 0.5

@dataclass
class GraphEdge:
    fact_id_a: int
    fact_id_b: int
    relationship: str
    confidence: float = 0.8
    note: str = ""`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'The flat fact store that MemoryGraph operates on top of.' },
        { href: '/services/personality',    label: 'Service', title: 'Personality Engine', desc: 'Graph facts feed into the personality prompt via MemoryManager.' },
        { href: '/memory',                  label: 'Feature', title: 'Memory Overview', desc: 'High-level explanation of Luna\'s three-tier memory system.' },
      ]} />
    </DocsLayout>
  );
}
