import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',    label: 'Overview' },
  { id: 'sqlite',      label: 'SQLite (default)' },
  { id: 'postgresql',  label: 'PostgreSQL / Supabase' },
  { id: 'mysql',       label: 'MySQL / MariaDB' },
  { id: 'mssql',       label: 'MS SQL Server' },
  { id: 'pool',        label: 'Connection pool' },
  { id: 'alembic',     label: 'Migrations (Alembic)' },
  { id: 'schema',      label: 'Schema overview' },
  { id: 'chroma',      label: 'ChromaDB (vectors)' },
  { id: 'backup',      label: 'Backup & restore' },
];

export default function DatabasePage() {
  return (
    <DocsLayout
      title="Database Integrations"
      description="SQLite, PostgreSQL, MySQL, and MS SQL Server — how to configure each, Alembic migrations, connection pooling, and ChromaDB for vector storage."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna uses <strong>SQLAlchemy</strong> as its ORM and supports four database
          backends: SQLite (default, zero-config), PostgreSQL, MySQL/MariaDB, and
          MS SQL Server. All use the same schema and the same migration path via
          Alembic.
        </p>
        <p>
          <strong>ChromaDB</strong> stores embedding vectors for semantic fact
          retrieval and episodic memory. It runs as a separate embedded database
          alongside the main relational store.
        </p>
        <table>
          <thead><tr><th>Database</th><th>Use case</th><th>Package</th></tr></thead>
          <tbody>
            <tr><td>SQLite</td><td>Local / development / single-user</td><td>Built-in (no extra deps)</td></tr>
            <tr><td>PostgreSQL</td><td>Production, Supabase, high concurrency</td><td><code>psycopg2-binary</code></td></tr>
            <tr><td>MySQL / MariaDB</td><td>Existing MySQL infrastructure</td><td><code>pymysql</code></td></tr>
            <tr><td>MS SQL Server</td><td>Enterprise / Azure SQL</td><td><code>pyodbc</code></td></tr>
            <tr><td>ChromaDB</td><td>Vector embeddings (all backends)</td><td><code>chromadb</code> (included)</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="sqlite">SQLite (default)</h2>
        <p>
          SQLite is the default and requires no configuration. The database file is
          created at <code>data/luna.db</code> on first run.
        </p>
        <CodeFile label=".env — SQLite (default)">
          <pre><code>{`# Leave DB_URL blank — SQLite is used automatically
# DB_URL=    ← not set

# Optional: change the file path
DB_PATH=data/luna.db

# Optional: custom data directory
LUNA_DATA_DIR=/path/to/luna-data`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          SQLite is fully supported for single-user personal deployments. For
          multi-user business deployments with concurrent writes, use PostgreSQL.
        </Callout>
        <h3>SQLite limitations</h3>
        <ul>
          <li>No connection pool (<code>DB_POOL_SIZE</code> is ignored).</li>
          <li>Write concurrency is limited by SQLite's file-level locking.</li>
          <li>Not suitable for multi-process deployments (Gunicorn with workers &gt; 1).</li>
        </ul>
      </section>

      <section>
        <h2 id="postgresql">PostgreSQL / Supabase</h2>
        <CodeFile label=".env">
          <pre><code>{`DB_URL=postgresql+psycopg2://user:password@localhost:5432/luna

# Supabase (pooler URL — recommended for serverless):
DB_URL=postgresql+psycopg2://postgres.xxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres`}</code></pre>
        </CodeFile>
        <CodeFile label="install">
          <pre><code>{`pip install psycopg2-binary`}</code></pre>
        </CodeFile>
        <h3>PostgreSQL-specific settings</h3>
        <CodeFile label=".env">
          <pre><code>{`DB_POOL_SIZE=10       # persistent connections in the pool
DB_MAX_OVERFLOW=20   # extra connections above pool_size under load
DB_POOL_TIMEOUT=30   # seconds to wait for a free connection
DB_POOL_RECYCLE=1800 # recycle connections every 30 min (prevents stale TCP)
DB_ECHO=false        # log every SQL statement (development only)`}</code></pre>
        </CodeFile>
        <h3>Supabase setup</h3>
        <ol>
          <li>Create a project at <code>supabase.com</code>.</li>
          <li>Go to <strong>Project Settings → Database → Connection string → Python</strong>.</li>
          <li>Copy the connection string into <code>DB_URL</code>.</li>
          <li>Run <code>alembic upgrade head</code> to create the schema.</li>
        </ol>
      </section>

      <section>
        <h2 id="mysql">MySQL / MariaDB</h2>
        <CodeFile label=".env">
          <pre><code>{`DB_URL=mysql+pymysql://user:password@localhost:3306/luna

# With charset (recommended):
DB_URL=mysql+pymysql://user:password@localhost:3306/luna?charset=utf8mb4`}</code></pre>
        </CodeFile>
        <CodeFile label="install">
          <pre><code>{`pip install pymysql`}</code></pre>
        </CodeFile>
        <CodeFile label="create the database (MySQL CLI)">
          <pre><code>{`CREATE DATABASE luna CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'luna_user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON luna.* TO 'luna_user'@'localhost';
FLUSH PRIVILEGES;`}</code></pre>
        </CodeFile>
        <Callout type="note">
          Always create the MySQL database with <code>utf8mb4</code> charset to
          support emoji and full Unicode in conversation content and memory facts.
        </Callout>
      </section>

      <section>
        <h2 id="mssql">MS SQL Server / Azure SQL</h2>
        <CodeFile label=".env — SQL Server">
          <pre><code>{`DB_URL=mssql+pyodbc://user:password@server/luna?driver=ODBC+Driver+17+for+SQL+Server`}</code></pre>
        </CodeFile>
        <CodeFile label=".env — Azure SQL">
          <pre><code>{`DB_URL=mssql+pyodbc://@myserver.database.windows.net/luna?driver=ODBC+Driver+17+for+SQL+Server&Authentication=ActiveDirectoryInteractive`}</code></pre>
        </CodeFile>
        <CodeFile label="install">
          <pre><code>{`pip install pyodbc
# Also install the ODBC driver: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server`}</code></pre>
        </CodeFile>
        <h3>Create the database (T-SQL)</h3>
        <CodeFile label="SQL Server Management Studio or Azure Data Studio">
          <pre><code>{`CREATE DATABASE luna COLLATE SQL_Latin1_General_CP1_CI_AS;
CREATE LOGIN luna_user WITH PASSWORD = 'YourPasswordHere';
USE luna;
CREATE USER luna_user FOR LOGIN luna_user;
ALTER ROLE db_owner ADD MEMBER luna_user;`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="pool">Connection pool</h2>
        <p>
          SQLAlchemy's connection pool is configured globally. These settings apply
          to PostgreSQL, MySQL, and MS SQL Server (not SQLite):
        </p>
        <table>
          <thead><tr><th>Env var</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>DB_POOL_SIZE</code></td><td>10</td><td>Persistent connections maintained at all times.</td></tr>
            <tr><td><code>DB_MAX_OVERFLOW</code></td><td>20</td><td>Extra connections allowed above pool_size during spikes.</td></tr>
            <tr><td><code>DB_POOL_TIMEOUT</code></td><td>30</td><td>Seconds to wait for a free connection before raising.</td></tr>
            <tr><td><code>DB_POOL_RECYCLE</code></td><td>1800</td><td>Max connection age in seconds (prevents stale TCP drops).</td></tr>
            <tr><td><code>DB_ECHO</code></td><td>false</td><td>Log every SQL statement to stdout (dev/debug only).</td></tr>
          </tbody>
        </table>
        <p>
          The total max connections = <code>DB_POOL_SIZE + DB_MAX_OVERFLOW</code>.
          For Supabase or PlanetScale with connection limits, reduce <code>DB_POOL_SIZE</code>
          to 5 and <code>DB_MAX_OVERFLOW</code> to 10.
        </p>
      </section>

      <section>
        <h2 id="alembic">Migrations (Alembic)</h2>
        <p>
          Luna uses Alembic for schema management. Run migrations after switching
          database backends or updating Luna.
        </p>
        <CodeFile label="terminal">
          <pre><code>{`# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history

# Roll back one step
alembic downgrade -1`}</code></pre>
        </CodeFile>
        <Callout type="note">
          Always run <code>alembic upgrade head</code> after changing <code>DB_URL</code>
          to a new backend. The first run creates all tables from scratch.
        </Callout>
        <h3>Creating a migration</h3>
        <CodeFile label="terminal">
          <pre><code>{`# After editing SQLAlchemy models in backend/models/database.py:
alembic revision --autogenerate -m "add my_new_column"
alembic upgrade head`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="schema">Schema overview</h2>
        <p>Key tables in <code>backend/models/database.py</code>:</p>
        <table>
          <thead><tr><th>Table</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>conversations</code></td><td>Conversation sessions with title and metadata.</td></tr>
            <tr><td><code>messages</code></td><td>Individual messages (role, content, timestamps).</td></tr>
            <tr><td><code>facts</code></td><td>Long/short-term memory facts with category, confidence, importance.</td></tr>
            <tr><td><code>fact_relationships</code></td><td>Typed graph edges between facts (CONTRADICTS, CONFIRMS, etc.).</td></tr>
            <tr><td><code>episodes</code></td><td>Conversation episode summaries with key fact IDs and embeddings.</td></tr>
            <tr><td><code>personality_state</code></td><td>Current mood and style preference floats.</td></tr>
            <tr><td><code>state_events</code></td><td>Historical state inferences for pattern learning.</td></tr>
            <tr><td><code>tasks</code></td><td>User tasks with due date, priority, and completion status.</td></tr>
            <tr><td><code>calendar_events</code></td><td>Scheduled events with start/end datetime.</td></tr>
            <tr><td><code>proactive_log</code></td><td>Record of proactive messages sent by the scheduler.</td></tr>
            <tr><td><code>audit_log</code></td><td>Tool call history with args, results, and conversation ID.</td></tr>
            <tr><td><code>contradiction_notes</code></td><td>Records of detected fact contradictions.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="chroma">ChromaDB (vectors)</h2>
        <p>
          ChromaDB stores embedding vectors for two purposes:
        </p>
        <ul>
          <li><strong><code>luna_facts</code></strong> — fact embeddings for semantic retrieval in <code>MemoryManager</code>.</li>
          <li><strong><code>luna_episodes</code></strong> — episode embeddings for long-range conversation recall in <code>MemoryGraph</code>.</li>
        </ul>
        <CodeFile label=".env">
          <pre><code>{`# ChromaDB storage path (relative to LUNA_DATA_DIR)
CHROMA_PATH=data/chroma    # default

# Embedding provider (used by ChromaDB ingestion)
EMBEDDING_PROVIDER=ollama  # or openai-compatible`}</code></pre>
        </CodeFile>
        <p>
          ChromaDB runs embedded in the same process — no separate server. Data is
          persisted to disk at <code>CHROMA_PATH</code>. Deleting this directory
          clears all vectors (facts and episodes remain in the relational DB but lose
          semantic search until re-embedded).
        </p>
        <Callout type="note">
          ChromaDB is independent of the relational backend — it always uses its own
          local persistent storage regardless of which SQL database you choose.
        </Callout>
      </section>

      <section>
        <h2 id="backup">Backup and restore</h2>
        <h3>SQLite</h3>
        <CodeFile label="terminal">
          <pre><code>{`# Backup
cp data/luna.db data/backups/luna-$(date +%Y%m%d).db

# Restore
cp data/backups/luna-20250601.db data/luna.db`}</code></pre>
        </CodeFile>
        <h3>PostgreSQL</h3>
        <CodeFile label="terminal">
          <pre><code>{`pg_dump luna > luna-backup.sql
psql luna < luna-backup.sql`}</code></pre>
        </CodeFile>
        <h3>ChromaDB</h3>
        <CodeFile label="terminal">
          <pre><code>{`# ChromaDB is a directory — copy the entire folder
cp -r data/chroma data/backups/chroma-$(date +%Y%m%d)`}</code></pre>
        </CodeFile>
        <p>
          Luna automatically creates daily backups of SQLite to <code>data/backups/</code>
          via the scheduler. For PostgreSQL and MySQL, configure your own backup strategy.
        </p>
      </section>

      <NextSteps items={[
        { href: '/variants',              label: 'Guide',   title: 'Personal vs Business', desc: 'Database considerations for each deployment variant.' },
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'How facts are stored and retrieved from the database.' },
        { href: '/services/scheduler',    label: 'Service', title: 'Scheduler', desc: 'daily_memory_compaction() and confidence_decay() run against the DB.' },
      ]} />
    </DocsLayout>
  );
}
