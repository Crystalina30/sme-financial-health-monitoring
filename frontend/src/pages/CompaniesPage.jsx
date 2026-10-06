import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../services/apiClient.js';

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');

  const companies = useQuery({ queryKey: ['companies'], queryFn: api.listCompanies });

  const createCompany = useMutation({
    mutationFn: () => api.createCompany({ name, industry: industry || null }),
    onSuccess: () => {
      setName('');
      setIndustry('');
      queryClient.invalidateQueries({ queryKey: ['companies'] });
    },
  });

  return (
    <div className="page">
      <h1>Your companies</h1>

      <section className="card">
        <h2>Add a company</h2>
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault();
            createCompany.mutate();
          }}
        >
          <div className="field">
            <label htmlFor="name">Company name</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="industry">Industry (optional)</label>
            <input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </div>
          <button type="submit" className="button" disabled={createCompany.isPending}>
            Add
          </button>
        </form>
        {createCompany.isError && (
          <p className="alert alert-error">{createCompany.error.message}</p>
        )}
      </section>

      {companies.isLoading && <p className="muted">Loading…</p>}
      {companies.isError && <p className="alert alert-error">{companies.error.message}</p>}

      {companies.data?.length === 0 && (
        <p className="muted">No companies yet. Add one above to begin.</p>
      )}

      <div className="card-grid">
        {companies.data?.map((company) => (
          <Link key={company.id} to={`/companies/${company.id}`} className="card card-link">
            <h3>{company.name}</h3>
            <p className="muted">{company.industry || 'Industry not recorded'}</p>
            <p className="muted">{company.currency_code}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
