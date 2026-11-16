import Link from 'next/link'
import DocsLayout from '../../../components/DocsLayout'
import { codebaseCategories, getCategoryById } from '../../../data/codebase'

export default function CategoryPage({ category }) {
  return (
    <DocsLayout
      title={`Codebase: ${category.label}`}
      description={category.description}
    >
      <section>
        <p>{category.description}</p>
      </section>

      <section className="grid-panel">
        {category.files.map((file) => (
          <Link key={file.slug} href={`/codebase/${category.id}/${file.slug}`} className="card-link">
            <div>
              <h2>{file.title}</h2>
              <p>{file.summary}</p>
            </div>
          </Link>
        ))}
      </section>
    </DocsLayout>
  )
}

export async function getStaticPaths() {
  return {
    paths: codebaseCategories.map((category) => ({ params: { category: category.id } })),
    fallback: false,
  }
}

export async function getStaticProps({ params }) {
  const category = getCategoryById(params.category)
  return {
    props: {
      category: category || null,
    },
  }
}
