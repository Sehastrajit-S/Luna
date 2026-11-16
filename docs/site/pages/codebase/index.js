import Link from 'next/link'
import DocsLayout from '../../components/DocsLayout'
import { codebaseCategories } from '../../data/codebase'

export default function CodebaseIndex() {
  return (
    <DocsLayout
      title="Codebase"
      description="Browse Luna implementation files by category, with dedicated documentation for each important source file."
    >
      <section>
        <p>
          This section documents the key files and implementation entrypoints for the Luna repository.
          Files are grouped by category so contributors can quickly find the right source area.
        </p>
      </section>

      <section className="grid-panel">
        {codebaseCategories.map((category) => (
          <Link key={category.id} href={`/codebase/${category.id}`} className="card-link">
            <div>
              <h2>{category.label}</h2>
              <p>{category.description}</p>
              <p className="file-count">{category.files.length} file{category.files.length === 1 ? '' : 's'}</p>
            </div>
          </Link>
        ))}
      </section>
    </DocsLayout>
  )
}
