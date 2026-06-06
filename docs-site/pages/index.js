import Head from 'next/head';
import Link from 'next/link';

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
    icon: ic(<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>),
    title: 'Vision', href: '/integrations#voice',
    desc: 'Screen and camera awareness. Luna builds temporal visual context without storing raw frames.',
  },
  {
    icon: ic(<><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></>),
    title: 'Automation', href: '/agent',
    desc: 'Launch apps, control the browser, manage Spotify, execute calendar tasks and desktop actions.',
  },
  {
    icon: ic(<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>),
    title: 'Dashboard', href: '/integrations#data',
    desc: 'Live news, markets, weather, and maps in a heads-up display widget layer.',
  },
  {
    icon: ic(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></>),
    title: 'Private by Default', href: '/integrations#platforms',
    desc: 'Inference runs on your machine via Ollama. Zero data leaves unless you opt into cloud features.',
  },
];

const steps = [
  { title: 'Speak or type', desc: 'Chat through the UI or trigger Luna by voice. Accepts text, voice, and vision frames as input.' },
  { title: 'Context assembled', desc: 'Memory facts, personality, calendar state, vision observations, and activity history are injected into the prompt.' },
  { title: 'LLM processes', desc: 'Your local Ollama model or any OpenAI-compatible API handles inference with a full context window.' },
  { title: 'Actions & response', desc: 'Luna streams the reply, executes tools, opens widgets, updates memory, and delivers voice output.' },
];


export default function Home() {
  return (
    <>
      <Head>
        <title>L.U.N.A. — Local AI Companion</title>
        <meta name="description" content="L.U.N.A. is a local-first AI companion with voice, memory, vision, and automation. Runs entirely on your machine." />
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
            <Link href="/" className="site-nav-brand" aria-label="L.U.N.A. home">
              <img src="/images/logo.svg" alt="" width={26} height={26} />
              <span className="site-nav-logo">L.U.N.A.</span>
            </Link>
            <div className="site-nav-links">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="site-nav-link">
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
              Local-first AI companion
            </div>
            <h1 className="lp-h1">
              The AI that<br />
              <span className="lp-gradient-text">knows you.</span>
            </h1>
            <p className="lp-subheading">
              L.U.N.A. runs entirely on your machine. Voice, memory, vision,
              and desktop automation with zero cloud dependency.
            </p>
            <div className="lp-hero-stats" aria-hidden="true">
              <span className="lp-stat"><span className="lp-stat-dot" />Open Source</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Local Inference</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Electron + React</span>
              <span className="lp-stat"><span className="lp-stat-dot" />FastAPI Backend</span>
            </div>
            <div className="lp-hero-actions">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-primary">
                <GitHubIcon />View on GitHub
              </a>
              <Link href="/downloads" className="lp-btn lp-btn-outline">
                Downloads
              </Link>
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

        {/* ── How it works ── */}
        <section className="lp-section">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Workflow</p>
            <h2 className="lp-section-h2">How L.U.N.A. works.</h2>
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

        {/* ── OSS CTA ── */}
        <section className="lp-oss">
          <div className="lp-oss-inner">
            <h2>Built in the open.</h2>
            <p>Free, open-source, and always will be. Inspect every line, fork it, or contribute.</p>
            <div className="lp-oss-actions">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-primary">
                <GitHubIcon />Star on GitHub
              </a>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="lp-footer">
          <div className="lp-footer-inner">
            <div className="lp-footer-brand">
              <img src="/images/logo.svg" alt="" width={22} height={22} />
              <div className="lp-footer-brand-text">
                <span className="lp-footer-name">L.U.N.A.</span>
                <span className="lp-footer-tagline">Large Unified Nexus Mind AI</span>
              </div>
            </div>
            <nav className="lp-footer-links">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer">GitHub</a>
              <Link href="/downloads">Downloads</Link>
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
