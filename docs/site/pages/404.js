import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';

export default function NotFound() {
  return (
    <DocsLayout
      title="Page Not Found"
      description="The page you are looking for does not exist."
    >
      <section>
        <h2>404 — Page missing</h2>
        <p>We could not find that page. Use the navigation to return to the main docs sections.</p>
        <p>
          <Link href="/" className="button">
            Back to Home
          </Link>
        </p>
      </section>
    </DocsLayout>
  );
}
