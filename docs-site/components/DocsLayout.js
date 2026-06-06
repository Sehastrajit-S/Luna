import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 14, height: 14 }}>
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
  </svg>
);

const ExternalArrow = () => (
  <svg viewBox="0 0 12 12" fill="currentColor" style={{ width: 10, height: 10, opacity: 0.4 }}>
    <path d="M3.5 3a.5.5 0 000 1H7.3L2.15 9.15a.5.5 0 00.7.7L8 4.7V8.5a.5.5 0 001 0v-5a.5.5 0 00-.5-.5h-5z" />
  </svg>
);

const SunIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </svg>
);

const MoonIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20.99 12.74A8.99 8.99 0 1111.26 3.01a7 7 0 009.73 9.73z" />
  </svg>
);

const navGroups = [
  {
    label: 'Overview',
    items: [
      { href: '/getting-started', label: 'Getting Started' },
      { href: '/downloads',       label: 'Downloads' },
      { href: '/architecture',    label: 'Architecture' },
      { href: '/workflow',        label: 'Workflow' },
    ],
  },
  {
    label: 'Features',
    items: [
      { href: '/voice',        label: 'Voice' },
      { href: '/memory',       label: 'Memory' },
      { href: '/agent',        label: 'Agent & Skills' },
      { href: '/integrations', label: 'Integrations' },
      { href: '/health',       label: 'Health Platforms' },
    ],
  },
  {
    label: 'Build with Luna',
    items: [
      { href: '/sdk-overview',              label: 'SDK Overview' },
      { href: '/services/llm',              label: 'LLM Service' },
      { href: '/services/memory-manager',   label: 'Memory Manager' },
      { href: '/services/personality',      label: 'Personality Engine' },
      { href: '/services/scheduler',        label: 'Scheduler' },
      { href: '/services/state-engine',     label: 'State Engine' },
      { href: '/services/command-parser',   label: 'Command Parser' },
      { href: '/services/tool-runner',      label: 'Tool Runner' },
      { href: '/services/memory-graph',     label: 'Memory Graph' },
      { href: '/mcp',                       label: 'MCP Servers' },
    ],
  },
  {
    label: 'Skills',
    items: [
      { href: '/skills',          label: 'Using Skills' },
      { href: '/skills-authoring',label: 'Building Skills' },
    ],
  },
  {
    label: 'UI Components',
    items: [
      { href: '/ui/chat',     label: 'Chat' },
      { href: '/ui/voice',    label: 'Voice Orb' },
      { href: '/ui/settings', label: 'Settings' },
      { href: '/ui/sidebar',  label: 'Sidebar & Layout' },
    ],
  },
  {
    label: 'Platform',
    items: [
      { href: '/cli',               label: 'CLI' },
      { href: '/environment',       label: 'Environment' },
      { href: '/database',          label: 'Database Setup' },
      { href: '/variants',          label: 'Personal vs Business' },
      { href: '/project-structure', label: 'Project Structure' },
      { href: '/api-reference',     label: 'API Reference' },
    ],
  },
  {
    label: 'Performance',
    items: [
      { href: '/benchmarks', label: 'Benchmarks' },
    ],
  },
  {
    label: 'Community',
    items: [
      { href: '/contributing',    label: 'Contributing' },
      { href: '/troubleshooting', label: 'Troubleshooting' },
    ],
  },
];

export default function DocsLayout({ title, description, toc, children }) {
  const router = useRouter();
  const [theme, setTheme] = useState('light');

  useEffect(() => {
    const saved = window.localStorage.getItem('luna-docs-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = saved || (prefersDark ? 'dark' : 'light');
    setTheme(initialTheme);
    document.documentElement.dataset.theme = initialTheme;
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem('luna-docs-theme', nextTheme);
  };

  const isActive = (href) =>
    router.pathname === href || router.asPath === href || router.asPath.startsWith(`${href}/`);

  return (
    <>
      <Head>
        <title>{title} — L.U.N.A. Docs</title>
        <meta name="description" content={description} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/images/logo.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </Head>

      <div className="docs-wrap">

        {/* Top bar */}
        <header className="docs-topbar">
          <div className="docs-topbar-inner">
            <div className="docs-topbar-left">
              <Link href="/" className="docs-topbar-brand">
                <img src="/images/logo.svg" alt="" width={22} height={22} />
                <span className="docs-topbar-logo">L.U.N.A.</span>
              </Link>
              <div className="docs-topbar-sep" />
              <span className="docs-topbar-label">Documentation</span>
            </div>
            <div className="docs-topbar-right">
              <button
                type="button"
                className="theme-toggle"
                onClick={toggleTheme}
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
              </button>
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="docs-topbar-link">
                <GitHubIcon /> GitHub
              </a>
              <Link href="/downloads" className="docs-topbar-cta">Downloads</Link>
              <Link href="/" className="docs-topbar-cta">← Home</Link>
            </div>
          </div>
        </header>

        <div className="docs-body">

          {/* Sidebar */}
          <aside className="docs-sidebar">
            <nav style={{ flex: 1, paddingTop: 8 }}>
              {navGroups.map((group) => (
                <div key={group.label} className="docs-nav-group">
                  <p className="docs-nav-group-label">{group.label}</p>
                  {group.items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`docs-nav-link${isActive(item.href) ? ' active' : ''}`}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              ))}
            </nav>

            <div className="docs-sidebar-footer">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer">
                <GitHubIcon /> GitHub <ExternalArrow />
              </a>
            </div>
          </aside>

          {/* Main */}
          <main className="docs-main">
            <div className="docs-main-layout">
              <div className="docs-main-content">
                <div className="docs-page-header">
                  <h1 className="docs-page-title">{title}</h1>
                  {description && <p className="docs-page-desc">{description}</p>}
                </div>
                <div className="docs-content">
                  {children}
                </div>
              </div>

              {toc && toc.length > 0 && (
                <aside className="docs-toc-panel">
                  <p className="docs-toc-label">On this page</p>
                  {toc.map((item) => (
                    <a key={item.id} href={`#${item.id}`} className="docs-toc-link">
                      {item.label}
                    </a>
                  ))}
                </aside>
              )}
            </div>
          </main>

        </div>
      </div>
    </>
  );
}
