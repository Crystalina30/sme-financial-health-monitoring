import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';
import './LoginPage.css';
import { pendingInvitationToken } from './JoinPage.jsx';

// Decorative glowing lines that run in from the screen edges to the card.
const TRACES = [
  { side: 'left', row: 1 },
  { side: 'left', row: 2 },
  { side: 'right', row: 1 },
  { side: 'right', row: 2 },
];

// The browser's own constraint checks (required, type="email") still decide
// what is valid; these only replace the browser's tooltip wording.
const FIELD_MESSAGES = {
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, for example name@company.com.',
  },
  password: {
    valueMissing: 'Enter your password.',
  },
};

function collectFieldErrors(form) {
  const errors = {};
  for (const input of form.querySelectorAll('input[name]')) {
    if (input.checkValidity()) continue;
    const messages = FIELD_MESSAGES[input.name] || {};
    if (input.validity.valueMissing) errors[input.name] = messages.valueMissing;
    else if (input.validity.typeMismatch) errors[input.name] = messages.typeMismatch;
    else errors[input.name] = input.validationMessage;
  }
  return errors;
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function EyeIcon({ crossed }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
      {crossed && <path d="m4 4 16 16" />}
    </svg>
  );
}

function BrandMark() {
  return (
    <svg className="login-brand-mark" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="1.5" y="1.5" width="45" height="45" rx="12" />
      <path className="login-brand-bars" d="M14 34v-6M22 34V22M30 34v-9M38 34V16" />
      <path className="login-brand-line" d="M12 24l9-7 8 5 10-9" />
    </svg>
  );
}

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [isShaking, setIsShaking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  function clearFieldError(field) {
    setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);

    const errors = collectFieldErrors(event.currentTarget);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      event.currentTarget.querySelector(':invalid')?.focus();
      setIsShaking(true);
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(pendingInvitationToken() ? '/join' : '/', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
      setIsShaking(true);
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleAnimationEnd(event) {
    if (event.animationName === 'login-shake') setIsShaking(false);
  }

  return (
    <div className="login-page">
      <div className="login-backdrop" aria-hidden="true">
        <span className="login-glow login-glow--a" />
        <span className="login-glow login-glow--b" />
      </div>

      <main className="login-stage">
        <div className="login-traces" aria-hidden="true">
          {TRACES.map(({ side, row }) => (
            <span key={`${side}-${row}`} className={`login-trace login-trace--${side} login-trace--row${row}`}>
              <span className="login-trace-line" />
              <span className="login-trace-dot" />
            </span>
          ))}
        </div>

        <div
          className={`login-card${isShaking ? ' is-shaking' : ''}`}
          onAnimationEnd={handleAnimationEnd}
        >
          <form
            className="login-form"
            onSubmit={handleSubmit}
            noValidate
            aria-busy={isSubmitting}
            aria-labelledby="login-title"
          >
            <h1 id="login-title" className="login-title login-reveal" style={{ '--i': 0 }}>
              Sign in
            </h1>

            {error && (
              <p className="login-alert" role="alert">
                {error}
              </p>
            )}

            <div className="login-field login-reveal" style={{ '--i': 1 }}>
              <label htmlFor="email" className="login-sr-only">
                Email address
              </label>
              <div className={`login-control${fieldErrors.email ? ' is-invalid' : ''}`}>
                <div className="login-control-inner">
                  <span className="login-icon">
                    <MailIcon />
                  </span>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    className="login-input"
                    placeholder="Email address"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      clearFieldError('email');
                    }}
                    aria-invalid={Boolean(fieldErrors.email)}
                    aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                    required
                  />
                </div>
              </div>
              {fieldErrors.email && (
                <p id="email-error" className="login-field-error">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div className="login-field login-reveal" style={{ '--i': 2 }}>
              <label htmlFor="password" className="login-sr-only">
                Password
              </label>
              <div className={`login-control${fieldErrors.password ? ' is-invalid' : ''}`}>
                <div className="login-control-inner">
                  <span className="login-icon">
                    <LockIcon />
                  </span>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    className="login-input login-input--with-toggle"
                    placeholder="Password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value);
                      clearFieldError('password');
                    }}
                    aria-invalid={Boolean(fieldErrors.password)}
                    aria-describedby={fieldErrors.password ? 'password-error' : undefined}
                    required
                  />
                  <button
                    type="button"
                    className="login-toggle"
                    onClick={() => setShowPassword((shown) => !shown)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-controls="password"
                  >
                    <EyeIcon crossed={showPassword} />
                  </button>
                </div>
              </div>
              {fieldErrors.password && (
                <p id="password-error" className="login-field-error">
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <button
              type="submit"
              className="login-submit login-reveal"
              style={{ '--i': 3 }}
              disabled={isSubmitting}
            >
              {isSubmitting && <span className="login-spinner" aria-hidden="true" />}
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>

            <p className="login-switch login-reveal" style={{ '--i': 4 }}>
              No account? <Link to="/register">Create one</Link>
            </p>
          </form>

          <aside className="login-panel" aria-label="About this application">
            <div className="login-panel-content">
              <BrandMark />
              <h2 className="login-panel-title">Welcome back</h2>
              <p className="login-panel-name">SME Financial Health Dashboard</p>
              <p className="login-panel-text">
                Track liquidity, profitability, solvency and efficiency in one place.
              </p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
