import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'chat',       label: 'Ask in chat' },
  { id: 'tab',        label: 'The News tab' },
  { id: 'categories', label: 'Categories' },
  { id: 'sources',    label: 'Sources' },
  { id: 'api',        label: 'API' },
];

export default function News() {
  return (
    <DocsLayout
      title="News"
      description="Current headlines with images, by category, in chat or in their own tab."
      toc={toc}
    >
      <section>
        <h2 id="chat">Ask in chat</h2>
        <p>
          Ask "what's the news?", "tech news" or "any sports headlines?". Luna answers with real headlines: each
          one has its image, source, how long ago it was published, and a link to the article. Buttons under the
          answer jump to another category.
        </p>
        <Callout type="tip" title="No API key needed">
          <p>News comes from public RSS feeds, so it works out of the box.</p>
        </Callout>
      </section>

      <section>
        <h2 id="tab">The News tab</h2>
        <p>
          <strong>News</strong> in the sidebar opens a feed you can browse without asking: pick a category at the
          top, scroll the stories, and click one to read it at the source. <strong>Refresh</strong> fetches the
          latest; otherwise stories are cached for 10 minutes.
        </p>
      </section>

      <section>
        <h2 id="categories">Categories</h2>
        <table>
          <thead><tr><th>Key</th><th>Covers</th></tr></thead>
          <tbody>
            <tr><td><code>top</code></td><td>Top stories</td></tr>
            <tr><td><code>world</code></td><td>World</td></tr>
            <tr><td><code>us</code></td><td>US</td></tr>
            <tr><td><code>business</code></td><td>Business and markets</td></tr>
            <tr><td><code>tech</code></td><td>Technology</td></tr>
            <tr><td><code>science</code></td><td>Science and environment</td></tr>
            <tr><td><code>health</code></td><td>Health</td></tr>
            <tr><td><code>sports</code></td><td>Sports</td></tr>
            <tr><td><code>entertainment</code></td><td>Entertainment and arts</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="sources">Sources</h2>
        <p>
          Every category mixes BBC, The Guardian and NPR, newest first, with no more than two stories from one
          source in a row. Headlines link to the publisher's site; Luna doesn't copy articles.
        </p>
      </section>

      <section>
        <h2 id="api">API</h2>
        <CodeFile label="GET /api/news">
          <pre><code>{`GET /api/news?category=tech&limit=12&refresh=false

{
  "category": "tech",
  "label": "Tech",
  "categories": [{ "key": "top", "label": "Top stories" }, …],
  "stories": [
    { "title": "…", "link": "…", "source": "BBC", "image": "…",
      "summary": "…", "published": "2026-11-16T09:30:00Z", "ago": "2h ago" }
  ]
}`}</code></pre>
        </CodeFile>
        <p><code>limit</code> is 1 to 40 (default 30). An unknown category falls back to <code>top</code>.</p>
      </section>

      <NextSteps items={[
        { href: '/store-prices', label: 'Feature', title: 'Store prices', desc: 'Compare a product across big stores.' },
        { href: '/agent', label: 'Agent', title: 'Agent & Skills', desc: 'How Luna decides what to run.' },
      ]} />
    </DocsLayout>
  );
}
