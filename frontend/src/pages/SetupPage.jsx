import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import Icon from '../components/Icon.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { useOrganisationQuery } from '../context/OrganisationContext.jsx';
import { api } from '../services/apiClient.js';

const CURRENCIES = ['MYR', 'SGD', 'IDR', 'THB', 'PHP', 'VND', 'INR', 'USD', 'EUR', 'GBP'];

/** Chooses one company, for an account that owned several before. */
function ChooseOrganisation({ candidates, onDone }) {
  const [chosen, setChosen] = useState(null);
  const select = useMutation({
    mutationFn: () => api.selectOrganisation(chosen),
    onSuccess: onDone,
  });

  return (
    <section className="card reveal setup-card">
      <h2>Choose your organisation</h2>
      <p className="muted">
        This account holds more than one company from before. Each account now monitors one
        SME. Choose the one that is yours; the others are kept unchanged and are not deleted.
      </p>
      <fieldset className="setup-choices">
        <legend className="visually-hidden">Company</legend>
        {candidates.map((company) => (
          <label key={company.id} className="setup-choice">
            <input
              type="radio"
              name="organisation"
              value={company.id}
              checked={chosen === company.id}
              onChange={() => setChosen(company.id)}
            />
            <span>
              <strong>{company.name}</strong>
              <span className="note">
                {[company.industry, company.currency_code].filter(Boolean).join(' · ')}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {select.isError && <p className="alert alert-error">{select.error.message}</p>}
      <button
        type="button"
        className="button"
        disabled={chosen === null || select.isPending}
        onClick={() => select.mutate()}
      >
        Use this organisation
      </button>
    </section>
  );
}

/** Someone invited to an existing organisation joins it instead. */
function JoinWithLink() {
  const navigate = useNavigate();
  const [link, setLink] = useState('');
  function go(event) {
    event.preventDefault();
    const text = link.trim();
    let token = text;
    try {
      token = new URL(text).searchParams.get('token') || text;
    } catch {
      /* a bare token was pasted */
    }
    navigate(`/join?token=${encodeURIComponent(token)}`);
  }
  return (
    <section className="card reveal setup-card">
      <h2>Joining your company?</h2>
      <p className="muted">
        If your CEO / Admin sent you an invitation link, open it, or paste it here.
      </p>
      <form className="inline-form" onSubmit={go}>
        <div className="field">
          <label htmlFor="invite-link">Invitation link</label>
          <input id="invite-link" value={link} onChange={(e) => setLink(e.target.value)} required />
        </div>
        <button type="submit" className="button button-quiet">
          Continue
        </button>
      </form>
    </section>
  );
}

/** One-time setup of the account's organisation. */
function CreateOrganisation({ onDone }) {
  const [form, setForm] = useState({ name: '', industry: '', currency_code: 'MYR' });
  const create = useMutation({
    mutationFn: () =>
      api.setUpOrganisation({
        name: form.name.trim(),
        industry: form.industry.trim() || null,
        currency_code: form.currency_code,
      }),
    onSuccess: onDone,
  });

  return (
    <section className="card reveal setup-card">
      <h2>Set up your organisation</h2>
      <p className="muted">
        Tell us about the business you will monitor. You do this once; the details can be
        changed later in Company settings.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        <div className="field">
          <label htmlFor="org-name">Organisation name</label>
          <input
            id="org-name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            maxLength={255}
          />
        </div>
        <div className="field">
          <label htmlFor="org-industry">Industry (optional)</label>
          <input
            id="org-industry"
            value={form.industry}
            onChange={(e) => setForm({ ...form, industry: e.target.value })}
            maxLength={120}
          />
        </div>
        <div className="field">
          <label htmlFor="org-currency">Reporting currency</label>
          <select
            id="org-currency"
            value={form.currency_code}
            onChange={(e) => setForm({ ...form, currency_code: e.target.value })}
          >
            {CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>
        {create.isError && <p className="alert alert-error">{create.error.message}</p>}
        <button type="submit" className="button" disabled={create.isPending}>
          <Icon name="check" />
          {create.isPending ? 'Saving…' : 'Save and continue'}
        </button>
      </form>
    </section>
  );
}

export default function SetupPage() {
  const query = useOrganisationQuery();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  useBreadcrumbs([{ label: 'Organisation setup' }]);

  async function done() {
    await queryClient.invalidateQueries({ queryKey: ['organisation'] });
    navigate('/', { replace: true });
  }

  const { status, candidates } = query.data;
  return (
    <div className="page setup-page">
      <div className="page-heading">
        <div>
          <h1>Welcome</h1>
          <p className="page-subtitle">One step before your financial overview.</p>
        </div>
      </div>
      {status === 'selection_required' ? (
        <ChooseOrganisation candidates={candidates} onDone={done} />
      ) : (
        <>
          <JoinWithLink />
          <CreateOrganisation onDone={done} />
        </>
      )}
    </div>
  );
}
