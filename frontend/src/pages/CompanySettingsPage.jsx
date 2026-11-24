import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import ConfirmDialog from '../components/ConfirmDialog.jsx';
import Icon from '../components/Icon.jsx';
import { useBreadcrumbs } from '../context/BreadcrumbContext.jsx';
import { ROLE_LABELS, useOrganisation } from '../context/OrganisationContext.jsx';
import { api } from '../services/apiClient.js';

const ROLE_HELP = {
  admin: 'Full access: dashboard, scores, analysis, deleting data, settings, users.',
  clerk: 'Financial data only: trial balances, records, reporting periods. No dashboard or scores.',
};

/** Who can use the system, in which role. CEO / Admin only. */
function MembersSection() {
  const queryClient = useQueryClient();
  const members = useQuery({ queryKey: ['members'], queryFn: api.listMembers });
  const [form, setForm] = useState({ email: '', role: 'clerk' });
  const [removing, setRemoving] = useState(null);
  // Every change here is also a new entry in the activity log.
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['members'] });
    queryClient.invalidateQueries({ queryKey: ['audit-log'] });
  };

  const invitations = useQuery({ queryKey: ['invitations'], queryFn: api.listInvitations });
  const [link, setLink] = useState(null);
  const invite = useMutation({
    mutationFn: () => api.createInvitation({ email: form.email.trim(), role: form.role }),
    onSuccess: (created) => {
      setLink({
        email: created.email,
        expires_at: created.expires_at,
        url: `${window.location.origin}/join?token=${encodeURIComponent(created.token)}`,
      });
      setForm({ email: '', role: 'clerk' });
      queryClient.invalidateQueries({ queryKey: ['invitations'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id) => api.revokeInvitation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invitations'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
    },
  });
  const change = useMutation({
    mutationFn: ({ id, role }) => api.updateMember(id, role),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id) => api.removeMember(id),
    onSuccess: () => {
      setRemoving(null);
      refresh();
    },
  });

  return (
    <section className="card reveal members-card" style={{ '--i': 1 }}>
      <h2>Users and roles</h2>
      <p className="muted">
        <strong>CEO / Admin</strong>: {ROLE_HELP.admin} <br />
        <strong>Finance Clerk</strong>: {ROLE_HELP.clerk}
      </p>
      {members.isError && <p className="alert alert-error">{members.error.message}</p>}
      {change.isError && <p className="alert alert-error">{change.error.message}</p>}
      <ul className="members-list">
        {(members.data || []).map((member) => (
          <li key={member.id}>
            <span>
              <strong>{member.full_name || member.email}</strong>
              {member.is_you && <span className="note-inline"> (you)</span>}
              <span className="note">
                {member.email}
                {member.is_owner && ' · set up the organisation'}
              </span>
            </span>
            <select
              aria-label={`Role of ${member.email}`}
              value={member.role}
              disabled={member.is_owner || change.isPending}
              onChange={(event) => change.mutate({ id: member.id, role: event.target.value })}
            >
              <option value="admin">{ROLE_LABELS.admin}</option>
              <option value="clerk">{ROLE_LABELS.clerk}</option>
            </select>
            {!member.is_owner && (
              <button
                type="button"
                className="button button-small button-quiet button-danger-quiet"
                aria-label={`Remove ${member.email}`}
                onClick={() => setRemoving(member)}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>

      <h3 className="members-subheading">Invite someone</h3>
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          invite.mutate();
        }}
      >
        <div className="field">
          <label htmlFor="member-email">Email address</label>
          <input
            id="member-email"
            type="email"
            required
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="member-role">Role</label>
          <select
            id="member-role"
            value={form.role}
            onChange={(event) => setForm({ ...form, role: event.target.value })}
          >
            <option value="clerk">{ROLE_LABELS.clerk}</option>
            <option value="admin">{ROLE_LABELS.admin}</option>
          </select>
        </div>
        <button type="submit" className="button" disabled={invite.isPending}>
          <Icon name="plus" />
          Create invitation
        </button>
      </form>
      <p className="field-hint">
        This creates a single-use link that expires in 7 days. Send it to the person yourself;
        they must sign in with that email address and accept it. You never set or see their
        password.
      </p>
      {invite.isError && <p className="alert alert-error">{invite.error.message}</p>}
      {link && (
        <div className="alert alert-info invite-link" role="status">
          <strong>Invitation link for {link.email}</strong> (shown once; it expires{' '}
          {new Date(link.expires_at).toLocaleDateString('en-GB')}):
          <code>{link.url}</code>
          <button
            type="button"
            className="button button-small button-quiet"
            onClick={() => navigator.clipboard?.writeText(link.url)}
          >
            Copy link
          </button>
        </div>
      )}

      {(invitations.data || []).length > 0 && (
        <>
          <h3 className="members-subheading">Invitations</h3>
          <ul className="members-list">
            {invitations.data.map((item) => (
              <li key={item.id}>
                <span>
                  <strong>{item.email}</strong>
                  <span className="note">
                    {ROLE_LABELS[item.role]} · {item.state}
                    {item.state === 'pending' &&
                      ` · expires ${new Date(item.expires_at).toLocaleDateString('en-GB')}`}
                  </span>
                </span>
                <span />
                {item.state === 'pending' ? (
                  <button
                    type="button"
                    className="button button-small button-quiet button-danger-quiet"
                    aria-label={`Revoke the invitation for ${item.email}`}
                    onClick={() => revoke.mutate(item.id)}
                  >
                    Revoke
                  </button>
                ) : (
                  <span />
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.full_name || removing.email}?`}
          confirmLabel="Remove user"
          busyLabel="Removing…"
          busy={remove.isPending}
          error={remove.isError ? remove.error.message : null}
          onCancel={() => {
            remove.reset();
            setRemoving(null);
          }}
          onConfirm={() => remove.mutate(removing.id)}
        >
          <p>
            They will no longer be able to open this organisation. Their account and the
            financial data they entered are kept.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}

const ACTION_LABELS = {
  'organisation.created': 'Set up the organisation',
  'company.updated': 'Changed company settings',
  'period.created': 'Created a reporting period',
  'period.updated': 'Changed a reporting period',
  'period.deleted': 'Deleted a reporting period and its data',
  'record.created': 'Entered financial data',
  'record.corrected': 'Corrected financial data',
  'trial_balance.imported': 'Imported a trial balance',
  'invitation.created': 'Invited a user',
  'invitation.revoked': 'Revoked an invitation',
  'invitation.accepted': 'Joined the organisation',
  'member.role_changed': 'Changed a role',
  'member.removed': 'Removed a user',
};

function describe(event) {
  const d = event.detail || {};
  if (d.period && d.revision) return `${d.period}, revision ${d.revision}`;
  if (d.period && d.to_revision) {
    const fields = Object.keys(d.changed || {});
    return `${d.period}, revision ${d.from_revision} → ${d.to_revision}` +
      (fields.length ? ` (${fields.join(', ')})` : '');
  }
  if (event.action === 'period.deleted') return `${d.label} (${(d.revisions || []).length} revisions)`;
  if (d.label) return d.label;
  if (d.email) return `${d.email}${d.role ? `, ${ROLE_LABELS[d.role] || d.role}` : ''}${d.to ? `, now ${ROLE_LABELS[d.to]}` : ''}`;
  if (d.changed) return Object.keys(d.changed).join(', ');
  return '';
}

/** Who changed what, newest first. Read-only. */
function ActivityLog() {
  const log = useQuery({ queryKey: ['audit-log'], queryFn: api.getAuditLog });
  return (
    <section className="card reveal members-card" style={{ '--i': 2 }}>
      <h2>Activity log</h2>
      <p className="muted">Every change to the financial data and to access, with who made it.</p>
      {log.isError && <p className="alert alert-error">{log.error.message}</p>}
      <ul className="activity-log">
        {(log.data || []).map((event) => (
          <li key={event.id}>
            <time dateTime={event.created_at}>
              {new Date(event.created_at).toLocaleString('en-GB')}
            </time>
            <span>
              <strong>{ACTION_LABELS[event.action] || event.action}</strong>
              <span className="note">{describe(event)}</span>
            </span>
            <span className="muted">{event.actor_email}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Edit the organisation's details. There is no way to add another one. */
export default function CompanySettingsPage() {
  const { organisation } = useOrganisation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: '', industry: '', registration_number: '', currency_code: '' });
  const [saved, setSaved] = useState(false);

  useBreadcrumbs([{ label: 'Financial Overview', to: '/overview' }, { label: 'Company Settings' }]);

  useEffect(() => {
    setForm({
      name: organisation.name,
      industry: organisation.industry || '',
      registration_number: organisation.registration_number || '',
      currency_code: organisation.currency_code,
    });
  }, [organisation]);

  const save = useMutation({
    mutationFn: () =>
      api.updateCompany(organisation.id, {
        name: form.name.trim(),
        industry: form.industry.trim() || null,
        registration_number: form.registration_number.trim() || null,
        currency_code: form.currency_code.trim().toUpperCase(),
      }),
    onSuccess: () => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ['organisation'] });
      queryClient.invalidateQueries({ queryKey: ['overview'] });
      queryClient.invalidateQueries({ queryKey: ['company'] });
      queryClient.invalidateQueries({ queryKey: ['audit-log'] });
    },
  });

  const field = (key, label, props = {}) => (
    <div className="field">
      <label htmlFor={`settings-${key}`}>{label}</label>
      <input
        id={`settings-${key}`}
        value={form[key]}
        onChange={(event) => {
          setSaved(false);
          setForm({ ...form, [key]: event.target.value });
        }}
        {...props}
      />
    </div>
  );

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>Company settings</h1>
          <p className="page-subtitle">The organisation this account monitors.</p>
        </div>
      </div>
      <section className="card reveal setup-card">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          {field('name', 'Organisation name', { required: true, maxLength: 255 })}
          {field('industry', 'Industry (optional)', { maxLength: 120 })}
          {field('registration_number', 'Registration number (optional)', { maxLength: 100 })}
          {field('currency_code', 'Reporting currency (3-letter code)', {
            required: true,
            minLength: 3,
            maxLength: 3,
            pattern: '[A-Za-z]{3}',
          })}
          <p className="field-hint">
            Changing the currency changes only the label shown with figures; amounts are not
            converted.
          </p>
          {save.isError && <p className="alert alert-error">{save.error.message}</p>}
          {saved && (
            <p className="identity-ok" role="status">
              <Icon name="check" /> Saved.
            </p>
          )}
          <button type="submit" className="button" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </section>
      <MembersSection />
      <ActivityLog />
    </div>
  );
}
