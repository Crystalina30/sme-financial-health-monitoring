import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', fullName: '', password: '' });
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) return <Navigate to="/companies" replace />;

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(form.email, form.fullName, form.password);
      navigate('/companies', { replace: true });
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <h1>Create an account</h1>

        {error && <p className="alert alert-error">{error}</p>}

        <label htmlFor="fullName">Full name</label>
        <input
          id="fullName"
          value={form.fullName}
          onChange={(event) => update('fullName', event.target.value)}
          required
        />

        <label htmlFor="email">Email address</label>
        <input
          id="email"
          type="email"
          value={form.email}
          onChange={(event) => update('email', event.target.value)}
          required
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          minLength={8}
          value={form.password}
          onChange={(event) => update('password', event.target.value)}
          required
        />
        <p className="field-hint">At least 8 characters.</p>

        <button type="submit" className="button" disabled={isSubmitting}>
          {isSubmitting ? 'Creating…' : 'Create account'}
        </button>

        <p className="muted">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
