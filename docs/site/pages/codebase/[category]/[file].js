import Link from 'next/link'
import DocsLayout from '../../../components/DocsLayout'
import { codebaseCategories, getCategoryById, getFileBySlug } from '../../../data/codebase'

export default function FilePage({ category, file }) {
  return (
    <DocsLayout
      title={`${file.title}`}
      description={file.summary}
    >
      <section>
        <div className="file-meta">
          <span className="badge">Category</span>
          <span>{category.label}</span>
        </div>
        <div className="file-meta">
          <span className="badge">Source</span>
          <span>{file.path}</span>
        </div>
      </section>

      <section>
        <h2>What it does</h2>
        <p>{file.summary}</p>
      </section>

      <section>
        <h2>Key responsibilities</h2>
        <ul>
          {file.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Related files</h2>
        <p>
          Explore other files in the <Link href={`/codebase/${category.id}`}>{category.label}</Link> category.
        </p>
      </section>
    </DocsLayout>
  )
}

export async function getStaticPaths() {
  const paths = []
  codebaseCategories.forEach((category) => {
    category.files.forEach((file) => {
      paths.push({ params: { category: category.id, file: file.slug } })
    })
  })
  return { paths, fallback: false }
}

export async function getStaticProps({ params }) {
  const category = getCategoryById(params.category)
  const file = getFileBySlug(params.category, params.file)
  return {
    props: {
      category: category || null,
      file: file || null,
    },
  }
}
