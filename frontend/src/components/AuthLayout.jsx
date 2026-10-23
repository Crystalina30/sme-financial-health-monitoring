import './AuthLayout.css';

// Decorative glowing lines that run in from the screen edges to the card.
const TRACES = [
  { side: 'left', row: 1 },
  { side: 'left', row: 2 },
  { side: 'right', row: 1 },
  { side: 'right', row: 2 },
];

function BrandMark() {
  return (
    <svg className="auth-brand-mark" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="1.5" y="1.5" width="45" height="45" rx="12" />
      <path className="auth-brand-bars" d="M14 34v-6M22 34V22M30 34v-9M38 34V16" />
      <path className="auth-brand-line" d="M12 24l9-7 8 5 10-9" />
    </svg>
  );
}

/**
 * Shared frame for the sign-in and registration pages
 */
export default function AuthLayout({ panelTitle, panelText, isShaking, onShakeEnd, children }) {
  function handleAnimationEnd(event) {
    if (event.animationName === 'auth-shake') onShakeEnd();
  }

  return (
    <div className="auth-page">
      <div className="auth-backdrop" aria-hidden="true">
        <span className="auth-glow auth-glow--a" />
        <span className="auth-glow auth-glow--b" />
      </div>

      <main className="auth-stage">
        <div className="auth-traces" aria-hidden="true">
          {TRACES.map(({ side, row }) => (
            <span key={`${side}-${row}`} className={`auth-trace auth-trace--${side} auth-trace--row${row}`}>
              <span className="auth-trace-line" />
              <span className="auth-trace-dot" />
            </span>
          ))}
        </div>

        <div
          className={`auth-frame${isShaking ? ' is-shaking' : ''}`}
          onAnimationEnd={handleAnimationEnd}
        >
          {children}

          <aside className="auth-panel" aria-label="About this application">
            <div className="auth-panel-content">
              <BrandMark />
              <h2 className="auth-panel-title">{panelTitle}</h2>
              <p className="auth-panel-name">SME Financial Health Dashboard</p>
              <p className="auth-panel-text">{panelText}</p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
