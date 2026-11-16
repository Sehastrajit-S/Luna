import Head from 'next/head';
import Link from 'next/link';
import { SITE_URL } from '../components/DocsLayout';

const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
  </svg>
);

const ic = (path) => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
    stroke="#a78bfa" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true">
    {path}
  </svg>
);

/* Dotted grid wave — pre-computed at module load */
const COLS = 32, ROWS = 18, GAP = 60, DOT = 3, DUR = 5, SPD = 0.24;
const cx = (COLS - 1) / 2, cy = (ROWS - 1) / 2;
const dots = [];
for (let r = 0; r < ROWS; r++) {
  for (let c = 0; c < COLS; c++) {
    const dist = Math.sqrt((c - cx) ** 2 + (r - cy) ** 2);
    dots.push({ r, c, delay: +(dist * SPD - DUR / 2).toFixed(2) });
  }
}

const features = [
  {
    icon: ic(<><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="8" y1="21" x2="16" y2="21"/></>),
    title: 'Voice', href: '/voice',
    desc: 'Wake-word detection and push-to-talk. Luna listens, understands, and speaks back with local TTS.',
  },
  {
    icon: ic(<><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></>),
    title: 'Memory', href: '/memory',
    desc: 'Persistent facts, personality state, and conversation summaries stored in local SQLite and ChromaDB.',
  },
  {
    icon: ic(<><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></>),
    title: 'Meeting mode', href: '/meeting-mode',
    desc: 'Record a meeting and get a timestamped transcript plus minutes: decisions, action items and open questions.',
  },
  {
    icon: ic(<><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></>),
    title: 'Automation', href: '/agent',
    desc: 'Launch apps, control the browser, manage Spotify, execute calendar tasks and desktop actions.',
  },
  {
    icon: ic(<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>),
    title: 'News & prices', href: '/news',
    desc: "Real headlines with images by category, and one product compared across Walmart, Costco, Target, Sam's Club and Safeway.",
  },
  {
    icon: ic(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></>),
    title: 'Yours, anywhere', href: '/setup',
    desc: 'Runs on your machine with Ollama or the cloud model you pick. Reach it from your phone over Tailscale, without opening it to the internet.',
  },
];

const steps = [
  { title: 'Speak or type', desc: 'Chat through the UI or trigger Luna by voice. Accepts text, voice and attached files.' },
  { title: 'Context assembled', desc: 'Memory facts, personality, calendar state, and activity history are injected into the prompt.' },
  { title: 'LLM processes', desc: 'Your local Ollama model or any OpenAI-compatible API handles inference with a full context window.' },
  { title: 'Actions & response', desc: 'Luna streams the reply, executes tools, opens widgets, updates memory, and delivers voice output.' },
];


const RELEASES = 'https://github.com/Sehastrajit-S/Luna/releases/latest';

const gallery = [
  { src: '/screenshots/meeting-minutes.png', w: 600, h: 1298, phone: true,
    alt: 'Luna meeting mode: AI-written meeting minutes with summary, decisions and action items',
    caption: 'Meeting minutes, written for you' },
  { src: '/screenshots/store-prices.png', w: 1280, h: 800,
    alt: 'Luna comparing the price of one product at Walmart, Costco, Target, Sam’s Club and Safeway',
    caption: 'Compare prices across five stores' },
  { src: '/screenshots/desktop-library.png', w: 1600, h: 1000,
    alt: 'Luna Library with every uploaded and AI-created file in one place',
    caption: 'Every file in one Library' },
  { src: '/screenshots/mobile-library.png', w: 780, h: 1688, phone: true,
    alt: 'Luna self-hosted AI assistant on a phone, showing the Library of files',
    caption: 'Same Luna on your phone' },
];

const modelGroups = [
  { label: 'Run locally', items: ['Ollama', 'LM Studio', 'llama.cpp', 'any OpenAI-compatible server'] },
  { label: 'Or use the cloud', items: ['Claude', 'Gemini', 'OpenAI', 'Groq', 'Mistral', 'Cohere', 'NVIDIA NIM', 'OpenRouter'] },
];

const platforms = [
  { name: 'Windows', file: 'Installer (.exe)', href: RELEASES },
  { name: 'macOS', file: 'Apple silicon & Intel (.dmg)', href: RELEASES },
  { name: 'Linux', file: 'AppImage, x86_64 & arm64', href: RELEASES },
  { name: 'Android', file: 'App (.apk)', href: RELEASES },
  { name: 'Docker', file: 'Server + web UI, any OS', href: '/docker' },
  { name: 'iPhone & iPad', file: 'In Safari: Add to Home Screen', href: '/setup#remote' },
];

const faqs = [
  { q: 'What is Luna?',
    a: 'Luna is a free, open-source AI assistant and agent engine that you run yourself. It chats, listens, remembers, writes meeting minutes, works with your files and connects to apps like GitHub, Google Workspace and Microsoft 365. Your conversations and files stay on your own hardware.' },
  { q: 'Is Luna free?',
    a: 'Yes. Luna is MIT-licensed and free to use, modify and self-host. Local models through Ollama cost nothing to run. If you choose a cloud model such as Claude or Gemini, that provider bills you for your own API key.' },
  { q: 'Can Luna run offline, without the cloud?',
    a: 'Yes. With a local model through Ollama, chat, memory, voice transcription and meeting minutes run entirely on your computer. Features that look things up online, such as web search, news and store prices, need an internet connection.' },
  { q: 'Which AI models does Luna support?',
    a: 'Local models through Ollama, LM Studio, llama.cpp or any OpenAI-compatible server, and cloud models from Anthropic (Claude), Google (Gemini), OpenAI, Groq, Mistral, Cohere, NVIDIA NIM and OpenRouter. You can switch models at any time in Settings.' },
  { q: 'Can I use Luna on my phone?',
    a: 'Yes. Open your Luna in any phone browser, or install the Android app, and connect to the computer running it privately over Tailscale. Nothing is exposed to the public internet.' },
  { q: 'Is my data private?',
    a: 'Luna stores chats, memory and files in a database on your own machine or server, and nothing is sent to the Luna project. If you pick a cloud model, your messages go only to the provider you chose.' },
  { q: 'How is Luna different from ChatGPT?',
    a: 'You host Luna yourself, choose any model including fully local ones, and keep your data. It is open source, so you can add skills, connect tools over MCP and change how it works.' },
  { q: 'What do I need to run Luna?',
    a: 'A Windows, macOS or Linux computer. The desktop app needs Python 3.10 or newer for its built-in server, or you can run the server with Docker. For local models, install Ollama; a GPU speeds things up, but small models also run on a CPU.' },
];

const FAQ_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: faqs.map((f) => ({
    '@type': 'Question',
    name: f.q,
    acceptedAnswer: { '@type': 'Answer', text: f.a },
  })),
};

const SEO_DESCRIPTION =
  'Luna is an open-source, self-hosted AI assistant. Run local LLMs with Ollama or use Claude, Gemini or OpenAI. Voice, memory, meeting notes, MCP and skills on desktop, web and phone, private over Tailscale.';

const SOFTWARE_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'Luna',
  description: SEO_DESCRIPTION,
  applicationCategory: 'ProductivityApplication',
  operatingSystem: 'Windows, macOS, Linux, Android, Docker',
  license: 'https://opensource.org/licenses/MIT',
  url: SITE_URL,
  downloadUrl: 'https://github.com/Sehastrajit-S/Luna/releases/latest',
  sameAs: ['https://github.com/Sehastrajit-S/Luna'],
  image: `${SITE_URL}/images/og.png`,
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
};

export default function Home() {
  return (
    <>
      <Head>
        <title>Luna: open-source, self-hosted AI assistant and agent engine</title>
        <meta name="description" content={SEO_DESCRIPTION} />
        <link rel="canonical" href={`${SITE_URL}/`} />
        <meta property="og:type" content="website" />
        <meta property="og:site_name" content="Luna" />
        <meta property="og:title" content="Luna: the open-source AI engine you own" />
        <meta property="og:description" content={SEO_DESCRIPTION} />
        <meta property="og:url" content={`${SITE_URL}/`} />
        <meta property="og:image" content={`${SITE_URL}/images/og.png`} />
        <meta property="og:image:width" content="1280" />
        <meta property="og:image:height" content="640" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Luna: the open-source AI engine you own" />
        <meta name="twitter:description" content={SEO_DESCRIPTION} />
        <meta name="twitter:image" content={`${SITE_URL}/images/og.png`} />
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: JSON.stringify(SOFTWARE_JSON_LD) }}
        />
        <script
          type="application/ld+json"
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: JSON.stringify(FAQ_JSON_LD) }}
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/images/logo.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
        <style>{`
          @keyframes dot-wave {
            0%, 100% {
              background: rgba(109,40,217,0.2);
              transform: scale(0.6);
              box-shadow: none;
            }
            50% {
              background: rgba(216,180,254,0.88);
              transform: scale(1.25);
              box-shadow: 0 0 7px 2px rgba(167,139,250,0.45);
            }
          }
        `}</style>
      </Head>

      <div className="lp-root">

        {/* ── Nav ── */}
        <nav className="site-nav">
          <div className="site-nav-inner">
            <Link href="/" className="site-nav-brand" aria-label="Luna home">
              <img src="/images/logo.svg" alt="" width={26} height={26} />
              <span className="site-nav-logo">Luna</span>
            </Link>
            <div className="site-nav-links">
              <a href="https://github.com/Sehastrajit-S/Luna" target="_blank" rel="noopener noreferrer" className="site-nav-link">
                <GitHubIcon /><span>GitHub</span>
              </a>
              <div className="site-nav-divider" aria-hidden="true" />
              <Link href="/workflow" className="site-nav-link"><span>Workflow</span></Link>
              <Link href="/downloads" className="site-nav-cta">Downloads</Link>
              <Link href="/getting-started" className="site-nav-cta">Docs →</Link>
            </div>
          </div>
        </nav>

        {/* ── Hero ── */}
        <section className="lp-hero" style={{ background: '#02020a', overflow: 'hidden' }}>

          {/* ── Dotted grid wave ── */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none',
          }}>
            {/* Dot grid — centered, overflows and gets clipped */}
            <div style={{
              position: 'absolute',
              top: '50%', left: '50%',
              width: COLS * GAP, height: ROWS * GAP,
              transform: 'translate(-50%, -50%)',
            }}>
              {dots.map((dot, i) => (
                <div key={i} style={{
                  position: 'absolute',
                  left: dot.c * GAP + (GAP - DOT) / 2,
                  top:  dot.r * GAP + (GAP - DOT) / 2,
                  width: DOT, height: DOT,
                  borderRadius: '50%',
                  background: 'rgba(109,40,217,0.2)',
                  animation: `dot-wave ${DUR}s ease-in-out ${dot.delay}s infinite`,
                }} />
              ))}
            </div>
            {/* Vignette — fades grid at edges, keeps centre bright */}
            <div style={{
              position: 'absolute', inset: 0,
              background: 'radial-gradient(ellipse 70% 75% at 50% 50%, transparent 10%, rgba(2,2,10,0.82) 100%)',
            }} />
          </div>

          {/* Bottom fade — blends hero into next section */}
          <div aria-hidden="true" style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            height: 220, pointerEvents: 'none',
            background: 'linear-gradient(to bottom, transparent, #02020a)',
            zIndex: 2,
          }} />

          {/* Hero text */}
          <div className="lp-hero-inner" style={{ position: 'relative', zIndex: 3 }}>
            <div className="lp-eyebrow">
              <span className="lp-badge">Open Source</span>
              Self-hosted AI assistant
            </div>
            <h1 className="lp-h1">
              The AI engine<br />
              <span className="lp-gradient-text">you own.</span>
            </h1>
            <p className="lp-subheading">
              Luna is a free, open-source AI assistant that runs on your own computer. Use local
              LLMs with Ollama or any cloud model, talk to it, let it take meeting notes, and reach
              it from your desktop, browser or phone.
            </p>
            <div className="lp-hero-stats" aria-hidden="true">
              <span className="lp-stat"><span className="lp-stat-dot" />Any model</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Runs locally</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Windows · macOS · Linux · Android</span>
              <span className="lp-stat"><span className="lp-stat-dot" />MIT licensed</span>
            </div>
            <div className="lp-hero-actions">
              <Link href="#download" className="lp-btn lp-btn-primary">
                Download Luna free
              </Link>
              <a href="https://github.com/Sehastrajit-S/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-outline">
                <GitHubIcon />View on GitHub
              </a>
              <Link href="/getting-started" className="lp-btn lp-btn-outline">
                Read the Docs →
              </Link>
            </div>
          </div>

        </section>

        {/* ── Features ── */}
        <section className="lp-section">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Capabilities</p>
            <h2 className="lp-section-h2">Everything you need from an AI.</h2>
            <p className="lp-section-sub">No subscriptions. No data harvesting. Just intelligence, locally.</p>
            <div className="lp-features-grid">
              {features.map((f) => (
                <Link key={f.title} href={f.href} className="lp-feature-card" style={{ textDecoration: 'none', cursor: 'pointer' }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 10, marginBottom: 16,
                    background: 'rgba(124,58,237,0.12)',
                    border: '1px solid rgba(139,92,246,0.22)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {f.icon}
                  </div>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* ── Gallery ── */}
        <section className="lp-section" aria-labelledby="see-it">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">See it</p>
            <h2 id="see-it" className="lp-section-h2">Your AI assistant, at work.</h2>
            <p className="lp-section-sub">Real screens from Luna: meeting minutes, price comparison, your files, and the phone app.</p>
            <div className="lp-gallery">
              {gallery.map((g) => (
                <figure key={g.src} className={`lp-shot${g.phone ? ' lp-shot-phone' : ' lp-shot-wide'}`}>
                  <img src={g.src} alt={g.alt} width={g.w} height={g.h} loading="lazy" decoding="async" />
                  <figcaption>{g.caption}</figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>

        {/* ── Any model ── */}
        <section className="lp-section" aria-labelledby="any-model">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Any model</p>
            <h2 id="any-model" className="lp-section-h2">Local LLMs or the cloud. Your choice.</h2>
            <p className="lp-section-sub">Run open models on your own hardware, or plug in your own API key. Switch any time in Settings.</p>
            <div className="lp-models">
              {modelGroups.map((g) => (
                <div key={g.label} className="lp-model-group">
                  <h3>{g.label}</h3>
                  <ul>{g.items.map((m) => <li key={m}>{m}</li>)}</ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="lp-section">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Workflow</p>
            <h2 className="lp-section-h2">How Luna works.</h2>
            <p className="lp-section-sub">Four stages, entirely on your machine.</p>
            <div className="lp-steps-grid">
              {steps.map((s, i) => (
                <div key={i} className="lp-step-card">
                  <div className="lp-step-num" aria-hidden="true">{i + 1}</div>
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '48px' }}>
              <Link href="/workflow" className="lp-btn lp-btn-outline" style={{ display: 'inline-flex' }}>
                See full workflow →
              </Link>
            </div>
          </div>
        </section>

        {/* ── Download ── */}
        <section className="lp-section" id="download" aria-labelledby="download-h">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Download</p>
            <h2 id="download-h" className="lp-section-h2">Get Luna for every device.</h2>
            <p className="lp-section-sub">Free downloads from the latest release. Run the server once, then use it anywhere.</p>
            <div className="lp-platforms">
              {platforms.map((p) => (
                p.href.startsWith('http')
                  ? <a key={p.name} href={p.href} className="lp-platform" target="_blank" rel="noopener noreferrer"><strong>{p.name}</strong><span>{p.file}</span></a>
                  : <Link key={p.name} href={p.href} className="lp-platform"><strong>{p.name}</strong><span>{p.file}</span></Link>
              ))}
            </div>
            <p className="lp-download-note">
              New to self-hosting? Follow the <Link href="/setup">step-by-step setup guide</Link>.
            </p>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section className="lp-section" aria-labelledby="faq">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">FAQ</p>
            <h2 id="faq" className="lp-section-h2">Questions about Luna.</h2>
            <div className="lp-faq">
              {faqs.map((f) => (
                <details key={f.q} className="lp-faq-item">
                  <summary><h3>{f.q}</h3></summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── OSS CTA ── */}
        <section className="lp-oss">
          <div className="lp-oss-inner">
            <h2>Built in the open.</h2>
            <p>Free, open-source, and always will be. Inspect every line, fork it, or contribute.</p>
            <div className="lp-oss-actions">
              <a href="https://github.com/Sehastrajit-S/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-primary">
                <GitHubIcon />Star on GitHub
              </a>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="lp-footer">
          <div className="lp-footer-inner">
            <div className="lp-footer-brand">
              <img src="/images/logo.svg" alt="Luna logo" width={22} height={22} />
              <div className="lp-footer-brand-text">
                <span className="lp-footer-name">Luna</span>
                <span className="lp-footer-tagline">The open-source AI engine you own</span>
              </div>
            </div>
            <nav className="lp-footer-links">
              <a href="https://github.com/Sehastrajit-S/Luna" target="_blank" rel="noopener noreferrer">GitHub</a>
              <Link href="/downloads">Downloads</Link>
              <Link href="/setup">Setup</Link>
              <Link href="/meeting-mode">Meeting mode</Link>
              <Link href="/workflow">Workflow</Link>
              <Link href="/getting-started">Docs</Link>
              <Link href="/architecture">Architecture</Link>
            </nav>
          </div>
        </footer>

      </div>
    </>
  );
}
