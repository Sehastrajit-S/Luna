import Link from 'next/link';

export function Callout({ type = 'info', title, children }) {
  const icons = { info: 'ℹ️', warn: '⚠️', tip: '💡', note: '📌' };
  return (
    <div className={`callout callout-${type}`}>
      <span className="callout-icon">{icons[type]}</span>
      <div className="callout-body">
        {title && <strong>{title}</strong>}
        {children}
      </div>
    </div>
  );
}

export function CodeFile({ label, children }) {
  return (
    <div className="code-file">
      <div className="code-file-label">
        <span className="code-file-dot" />
        {label}
      </div>
      {children}
    </div>
  );
}

export function Steps({ children }) {
  return <div className="doc-steps">{children}</div>;
}

export function Step({ num, title, children }) {
  return (
    <div className="doc-step">
      <div className="doc-step-num">{num}</div>
      <div className="doc-step-body">
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  );
}

export function PropTable({ rows }) {
  return (
    <table className="prop-table">
      <thead>
        <tr>
          <th>Key</th>
          <th>Default</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            <td>{row.key}</td>
            <td>
              {row.default ? (
                <span className="badge-def">{row.default}</span>
              ) : row.required ? (
                <span className="badge-req">required</span>
              ) : (
                <span className="badge-opt">optional</span>
              )}
            </td>
            <td>{row.desc}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function NextSteps({ items }) {
  return (
    <nav className="next-steps" aria-label="Next steps">
      {items.map((item) => (
        <Link key={item.href} href={item.href} className="next-step-card">
          <p className="next-step-label">{item.label}</p>
          <h4>{item.title}</h4>
          <p>{item.desc}</p>
        </Link>
      ))}
    </nav>
  );
}
