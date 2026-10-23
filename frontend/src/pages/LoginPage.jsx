import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import AuthField, { collectFieldErrors } from '../components/AuthField.jsx';
import AuthLayout from '../components/AuthLayout.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const FIELD_MESSAGES = {
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, for example name@company.com.',
  },
  password: {
    valueMissing: 'Enter your password.',
  },
};

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [isShaking, setIsShaking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) return <Navigate to="/companies" replace />;

  function clearFieldError(field) {
    setFieldErrors((previous) => ({ ...previous, [field]: undefined }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);

    const errors = collectFieldErrors(event.currentTarget, FIELD_MESSAGES);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      event.currentTarget.querySelector(`[name="${Object.keys(errors)[0]}"]`)?.focus();
      setIsShaking(true);
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate('/companies', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
      setIsShaking(true);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout
      panelTitle="Welcome back"
      panelText="Track liquidity, profitability, solvency and efficiency in one place."
      isShaking={isShaking}
      onShakeEnd={() => setIsShaking(false)}
    >
      <form
        className="auth-form"
        onSubmit={handleSubmit}
        noValidate
        aria-busy={isSubmitting}
        aria-labelledby="auth-title"
      >
        <h1 id="auth-title" className="auth-title auth-reveal" style={{ '--i': 0 }}>
          Sign in
        </h1>

        {error && (
          <p className="auth-alert" role="alert">
            {error}
          </p>
        )}

        <AuthField
          id="email"
          label="Email address"
          icon="mail"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(value) => {
            setEmail(value);
            clearFieldError('email');
          }}
          error={fieldErrors.email}
          index={1}
          required
        />

        <AuthField
          id="password"
          label="Password"
          icon="lock"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(value) => {
            setPassword(value);
            clearFieldError('password');
          }}
          error={fieldErrors.password}
          revealable
          index={2}
          required
        />

        <button
          type="submit"
          className="auth-submit auth-reveal"
          style={{ '--i': 3 }}
          disabled={isSubmitting}
        >
          {isSubmitting && <span className="auth-spinner" aria-hidden="true" />}
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>

        <p className="auth-switch auth-reveal" style={{ '--i': 4 }}>
          No account? <Link to="/register">Create one</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
