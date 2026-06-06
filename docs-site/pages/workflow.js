import { useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';

/* Dot grid — same wave system as landing page hero */
const COLS = 32, ROWS = 18, GAP = 60, DOT = 3, DUR = 5, SPD = 0.24;
const cx = (COLS - 1) / 2, cy = (ROWS - 1) / 2;
const wfDots = [];
for (let r = 0; r < ROWS; r++) {
  for (let c = 0; c < COLS; c++) {
    const dist = Math.sqrt((c - cx) ** 2 + (r - cy) ** 2);
    wfDots.push({ r, c, delay: +(dist * SPD - DUR / 2).toFixed(2) });
  }
}

const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" style={{ width: 18, height: 18 }}>
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
  </svg>
);

const workflowSteps = [
  {
    tag: 'Step 01 — Input',
    title: 'You speak, type, or trigger.',
    desc: 'Luna accepts input through the chat UI, push-to-talk voice, wake-word detection, or scheduled proactive follow-ups. On desktop, screen and camera frames can be submitted to the vision pipeline.',
    pills: ['Chat UI', 'Push-to-Talk', 'Wake Word', 'Vision Frames', 'Scheduled Triggers'],
  },
  {
    tag: 'Step 02 — Context Assembly',
    title: 'Every relevant signal is gathered.',
    desc: 'Before calling the LLM, Luna assembles a rich context window. Memory facts, personality state, active activities, current calendar tasks, recent vision observations, and conversation history are all injected — giving the model full situational awareness.',
    pills: ['Memory Facts', 'Personality', 'Calendar & Tasks', 'Vision Summary', 'Conversation History', 'Live Dashboard Data'],
  },
  {
    tag: 'Step 03 — LLM Inference',
    title: 'Your local model processes the request.',
    desc: 'The assembled prompt is sent to your configured LLM provider — local Ollama by default, or any OpenAI-compatible endpoint. The model streams a structured response containing answer tokens, tool calls, and bracket commands.',
    pills: ['Ollama (local)', 'OpenAI-compatible API', 'num_ctx: 8192', 'Streaming SSE'],
  },
  {
    tag: 'Step 04 — Tool Execution',
    title: 'Luna acts on what it decides.',
    desc: 'Structured tool calls and bracket commands are parsed from the stream. Luna can search the web, fetch pages, control Spotify, launch applications, manage calendar tasks, open dynamic widget overlays, generate 3D scenes, and display map overlays — all with per-tool permission controls.',
    pills: ['Web Search', 'Web Fetch', 'Spotify Control', 'App Launch', 'Calendar', 'Dynamic Widgets', '3D Scenes', 'Maps'],
  },
  {
    tag: 'Step 05 — Memory Update',
    title: 'Facts and context are persisted.',
    desc: 'After each exchange, background processes extract new facts from the conversation, update personality vectors, and compact long conversations into summaries. Everything is stored locally in SQLite and ChromaDB — no external database, no cloud sync.',
    pills: ['SQLite', 'ChromaDB Embeddings', 'Fact Extraction', 'Personality Update', 'Conversation Compaction'],
  },
  {
    tag: 'Step 06 — Privacy First',
    title: 'Nothing leaves your machine by default.',
    desc: 'Inference, memory, vision, and voice processing all run locally. Cloud APIs (news, markets, Spotify) are opt-in and only contacted for the features they power. Your conversations, facts, and preferences are yours.',
    pills: ['Local Inference', 'Local Storage', 'No Telemetry', 'Opt-in Cloud Only'],
  },
];

export default function Workflow() {
  useEffect(() => {
    const steps = document.querySelectorAll('.wf-step');
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('wf-visible');
          io.unobserve(e.target);
        }
      }),
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' }
    );
    steps.forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, []);

  return (
    <>
      <Head>
        <title>Workflow — L.U.N.A.</title>
        <meta name="description" content="How L.U.N.A. works: input, context assembly, LLM inference, tool execution, memory, and privacy." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/images/logo.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
        <style>{`
          @keyframes dot-wave {
            0%, 100% { background: rgba(109,40,217,0.2); transform: scale(0.6); box-shadow: none; }
            50%       { background: rgba(216,180,254,0.88); transform: scale(1.25); box-shadow: 0 0 7px 2px rgba(167,139,250,0.45); }
          }
          body { background: #030306; }
        `}</style>
      </Head>

      {/* ── Fixed full-page dot grid ── */}
      <div aria-hidden="true" style={{
        position: 'fixed', inset: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none',
      }}>
        <div style={{
          position: 'absolute',
          top: '50%', left: '50%',
          width: COLS * GAP, height: ROWS * GAP,
          transform: 'translate(-50%, -50%)',
        }}>
          {wfDots.map((dot, i) => (
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
        {/* Soft edge vignette */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse 85% 85% at 50% 50%, transparent 15%, rgba(3,3,6,0.55) 100%)',
        }} />
      </div>

      {/* ── Page content ── */}
      <div className="wf-root" style={{ position: 'relative', zIndex: 1, background: 'transparent' }}>

        {/* ── Nav ── */}
        <nav className="site-nav" aria-label="Main navigation">
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
              <Link href="/" className="site-nav-link"><span>Home</span></Link>
              <Link href="/downloads" className="site-nav-cta">Downloads</Link>
              <Link href="/getting-started" className="site-nav-cta">Docs →</Link>
            </div>
          </div>
        </nav>

        {/* ── Hero ── */}
        <section className="wf-hero" style={{ background: 'transparent' }}>
          <div className="wf-hero-inner">
            <p className="wf-eyebrow">How it works</p>
            <h1 className="wf-h1">
              Six stages.<br />
              <span style={{
                background: 'linear-gradient(135deg, #a78bfa 0%, #8b5cf6 50%, #c4b5fd 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                One machine.
              </span>
            </h1>
            <p className="wf-sub">
              From your first word to the final response, every step of how L.U.N.A. processes,
              acts, and learns. Entirely local.
            </p>
          </div>
        </section>

        {/* ── Flow Steps ── */}
        <div className="wf-flow" style={{ background: 'transparent' }}>
          <p className="wf-flow-title">Request lifecycle</p>

          {workflowSteps.map((step, i) => (
            <div key={i} className="wf-step">
              <div className="wf-step-left">
                <div className="wf-step-circle">{i + 1}</div>
                {i < workflowSteps.length - 1 && (
                  <div className="wf-step-line" aria-hidden="true" />
                )}
              </div>

              <div className="wf-step-right">
                <span className="wf-step-tag">{step.tag}</span>
                <h2>{step.title}</h2>
                <p>{step.desc}</p>
                <div className="wf-pills">
                  {step.pills.map((pill) => (
                    <span key={pill} className="wf-pill">{pill}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* ── CTA ── */}
        <section className="wf-cta-section" style={{ background: 'transparent' }}>
          <h2>Ready to run it?</h2>
          <p>
            Get Luna running locally in minutes with the setup guide,
            or explore the source on GitHub.
          </p>
          <div className="wf-cta-actions">
            <Link href="/getting-started" className="lp-btn lp-btn-primary">
              Get Started →
            </Link>
            <a
              href="https://github.com/Sehastrajit/Luna"
              target="_blank"
              rel="noopener noreferrer"
              className="lp-btn lp-btn-outline"
            >
              <GitHubIcon />
              View Source
            </a>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="lp-footer" style={{ background: '#030306', position: 'relative', zIndex: 2 }}>
          <div className="lp-footer-inner">
            <div className="lp-footer-brand">
              <img src="/images/logo.svg" alt="" width={22} height={22} />
              <div className="lp-footer-brand-text">
                <span className="lp-footer-name">L.U.N.A.</span>
                <span className="lp-footer-tagline">Large Unified Nexus Mind AI</span>
              </div>
            </div>
            <nav className="lp-footer-links" aria-label="Footer navigation">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer">GitHub</a>
              <Link href="/downloads">Downloads</Link>
              <Link href="/">Home</Link>
              <Link href="/getting-started">Docs</Link>
              <Link href="/architecture">Architecture</Link>
            </nav>
          </div>
        </footer>

      </div>
    </>
  );
}
