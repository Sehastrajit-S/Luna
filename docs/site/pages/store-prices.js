import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, PropTable, NextSteps } from '../components/Docs';

const toc = [
  { id: 'use',      label: 'Compare a product' },
  { id: 'sources',  label: 'Where prices come from' },
  { id: 'matching', label: 'Matching the same product' },
  { id: 'settings', label: 'Settings' },
];

export default function StorePrices() {
  return (
    <DocsLayout
      title="Store prices"
      description="Compare one product's price at Walmart, Costco, Target, Sam's Club and Safeway."
      toc={toc}
    >
      <section>
        <h2 id="use">Compare a product</h2>
        <p>
          Click <strong>+</strong> → <strong>Skills</strong> → <strong>Store prices</strong> and type the product, or
          just ask: "compare prices for Tide Pods 81 count" or "where is Kirkland paper towels cheapest?".
        </p>
        <p>Luna shows a card per store with its logo, the product it found, the price, and a link. The cheapest matching offer is marked.</p>
        <figure className="doc-figure">
          <img src="/screenshots/store-prices.png" alt="Price comparison cards for one product at several stores" />
          <figcaption>One product, five stores.</figcaption>
        </figure>
        <figure className="doc-figure" style={{ maxWidth: 320, marginLeft: 'auto', marginRight: 'auto' }}>
          <img src="/screenshots/plus-menu.png" alt="The + menu with Attach, Skills and Meeting mode" />
          <figcaption>The <strong>+</strong> menu holds Attach, Skills and Meeting mode.</figcaption>
        </figure>
      </section>

      <section>
        <h2 id="sources">Where prices come from</h2>
        <table>
          <thead><tr><th>Mode</th><th>When</th><th>What you get</th></tr></thead>
          <tbody>
            <tr><td><strong>Google Shopping</strong> via SerpApi</td><td>A SerpApi key is set</td><td>Live prices for your area. The free plan covers 100 searches a month.</td></tr>
            <tr><td><strong>Free web search</strong></td><td>No key</td><td>Searches each store's own site. Prices may be missing or out of date, so the answer says so.</td></tr>
          </tbody>
        </table>
        <Callout type="tip" title="Add a key">
          <p>Get a free key at serpapi.com and paste it in <strong>Settings → Integrations</strong>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="matching">Matching the same product</h2>
        <ul>
          <li>Results must match most of the words you asked for, and the brand (the first word) has to match, so "Brawny" never stands in for "Kirkland".</li>
          <li>Pack size matters: a bigger pack is shown, but it's never called the cheapest when sizes differ.</li>
          <li>Stores with no match say "not found" instead of showing something unrelated.</li>
        </ul>
      </section>

      <section>
        <h2 id="settings">Settings</h2>
        <PropTable rows={[
          { key: 'serpapi_api_key', default: '""', desc: 'SerpApi key for Google Shopping. Empty uses the free web search.' },
          { key: 'shopping_location', default: '""', desc: 'Where to look up prices, e.g. "Phoenix, Arizona, United States".' },
          { key: 'shopping_max_searches', default: '3', desc: 'Searches one comparison may use: one general search, then follow-ups for stores it missed.' },
        ]} />
        <p>See <Link href="/environment">Environment</Link> for all settings.</p>
      </section>

      <NextSteps items={[
        { href: '/skills', label: 'Skills', title: 'Using Skills', desc: 'Pick a skill from the + menu.' },
        { href: '/news', label: 'Feature', title: 'News', desc: 'Headlines by category.' },
      ]} />
    </DocsLayout>
  );
}
