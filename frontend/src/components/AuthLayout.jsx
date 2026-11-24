import ThemeToggle from './ThemeToggle.jsx';
import './AuthLayout.css';

// Decorative glowing lines that run in from the screen edges to the card.
const TRACES = [
  { side: 'left', row: 1 },
  { side: 'left', row: 2 },
  { side: 'right', row: 1 },
  { side: 'right', row: 2 },
];

const PANEL_COPY = {
  login: {
    title: 'Welcome back',
    text: 'Track liquidity, profitability, solvency and efficiency in one place.',
  },
  register: {
    title: 'Get started',
    text: 'Create an account to set up your organisation and assess its financial health.',
  },
};

/**
 * Shared frame for the sign-in and registration pages. Both forms stay in the
 * card as children, side by side, and `mode` decides which one the panel
 * leaves uncovered: it sits over the registration form while signing in, and
 * slides across to sit over the sign-in form while registering.
 */
export default function AuthLayout({ mode, isShaking, onShakeEnd, children }) {
  function handleAnimationEnd(event) {
    if (event.animationName === 'auth-shake') onShakeEnd();
  }

  return (
    <div className="auth-page">
      <div className="auth-backdrop" aria-hidden="true">
        <span className="auth-glow auth-glow--a" />
        <span className="auth-glow auth-glow--b" />
      </div>

      <ThemeToggle className="auth-theme-toggle" />

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

          <aside
            className={`auth-panel auth-panel--${mode}`}
            aria-label="About this application"
          >
            <div className="auth-panel-inner">
              <div className="auth-panel-copy">
                {Object.entries(PANEL_COPY).map(([copyMode, { title, text }]) => (
                  <div
                    key={copyMode}
                    className={`auth-panel-content auth-panel-content--${copyMode}${
                      copyMode === mode ? ' is-active' : ''
                    }`}
                    aria-hidden={copyMode !== mode}
                  >
                    <h2 className="auth-panel-title">{title}</h2>
                    <p className="auth-panel-name">SME Financial Health Dashboard</p>
                    <p className="auth-panel-text">{text}</p>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
