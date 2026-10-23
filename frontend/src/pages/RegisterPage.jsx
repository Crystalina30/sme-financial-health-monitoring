import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import AuthField, { collectFieldErrors } from '../components/AuthField.jsx';
import AuthLayout from '../components/AuthLayout.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const FIELD_MESSAGES = {
  fullName: {
    valueMissing: 'Enter your full name.',
  },
  email: {
    valueMissing: 'Enter your email address.',
    typeMismatch: 'Enter a valid email address, for example name@company.com.',
  },
  password: {
    valueMissing: 'Choose a password.',
    tooShort: 'Use at least 8 characters.',
  },
};

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', fullName: '', password: '' });
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [isShaking, setIsShaking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) return <Navigate to="/companies" replace />;

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
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
      await register(form.email, form.fullName, form.password);
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
      panelTitle="Get started"
      panelText="Create an account to add your companies and assess their financial health."
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
          Create an account
        </h1>

        {error && (
          <p className="auth-alert" role="alert">
            {error}
          </p>
        )}

        <AuthField
          id="fullName"
          label="Full name"
          icon="user"
          autoComplete="name"
          value={form.fullName}
          onChange={(value) => update('fullName', value)}
          error={fieldErrors.fullName}
          index={1}
          required
        />

        <AuthField
          id="email"
          label="Email address"
          icon="mail"
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={(value) => update('email', value)}
          error={fieldErrors.email}
          index={2}
          required
        />

        <AuthField
          id="password"
          label="Password"
          icon="lock"
          type="password"
          autoComplete="new-password"
          minLength={8}
          value={form.password}
          onChange={(value) => update('password', value)}
          error={fieldErrors.password}
          hint="At least 8 characters."
          revealable
          index={3}
          required
        />

        <button
          type="submit"
          className="auth-submit auth-reveal"
          style={{ '--i': 4 }}
          disabled={isSubmitting}
        >
          {isSubmitting && <span className="auth-spinner" aria-hidden="true" />}
          {isSubmitting ? 'Creating…' : 'Create account'}
        </button>

        <p className="auth-switch auth-reveal" style={{ '--i': 5 }}>
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
