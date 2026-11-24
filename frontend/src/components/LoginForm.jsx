import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';
import useFormActivation from '../hooks/useFormActivation.js';
import AuthField, { collectFieldErrors } from './AuthField.jsx';
import { pendingInvitationToken } from '../pages/JoinPage.jsx';

const FIELD_MESSAGES = {
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, for example name@company.com.',
  },
  password: {
    valueMissing: 'Enter your password.',
  },
};

export default function LoginForm({ active, onFailure }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const titleRef = useFormActivation(active, () => {
    setPassword('');
    setError(null);
    setFieldErrors({});
  });

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
      onFailure();
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(pendingInvitationToken() ? '/join' : '/', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
      onFailure();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form
      className={`auth-form auth-form--login${active ? ' is-active' : ''}`}
      onSubmit={handleSubmit}
      noValidate
      aria-busy={isSubmitting}
      aria-labelledby="login-title"
      aria-hidden={!active}
      inert={active ? undefined : ''}
    >
      <h1
        id="login-title"
        ref={titleRef}
        tabIndex={-1}
        className="auth-title auth-reveal"
        style={{ '--i': 0 }}
      >
        Sign in
      </h1>

      {error && (
        <p className="auth-alert" role="alert">
          {error}
        </p>
      )}

      <AuthField
        id="login-email"
        name="email"
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
        id="login-password"
        name="password"
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
  );
}
