import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ROLE_LABELS } from '../context/OrganisationContext.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { api } from '../services/apiClient.js';

const PENDING_KEY = 'fyp_pending_invitation';

/** The invitation waiting to be accepted after signing in, if any. */
export function pendingInvitationToken() {
  try {
    return sessionStorage.getItem(PENDING_KEY);
  } catch {
    return null;
  }
}

function rememberToken(token) {
  try {
    sessionStorage.setItem(PENDING_KEY, token);
  } catch {
    /* private mode: the user can open the link again after signing in */
  }
}

function forgetToken() {
  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    /* nothing to do */
  }
}

/**
 * Accepting an invitation link. Joining always needs the signed-in person to
 * accept explicitly, with the email the invitation was issued to.
 */
export default function JoinPage() {
  const [params] = useSearchParams();
  const token = params.get('token') || pendingInvitationToken();
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (token) rememberToken(token);
  }, [token]);

  const preview = useQuery({
    queryKey: ['invitation', token],
    queryFn: () => api.previewInvitation(token),
    enabled: Boolean(user && token),
    retry: false,
  });
  const accept = useMutation({
    mutationFn: () => api.acceptInvitation(token),
    onSuccess: async () => {
      forgetToken();
      setAccepted(true);
      await queryClient.invalidateQueries({ queryKey: ['organisation'] });
      navigate('/', { replace: true });
    },
  });

  let body;
  if (!token) {
    body = <p className="alert alert-error">This page needs an invitation link.</p>;
  } else if (isLoading) {
    body = <p className="muted">Loading…</p>;
  } else if (!user) {
    body = (
      <>
        <p>
          You have an invitation to join an organisation. Sign in, or create an account, with
          the email address the invitation was sent to; you will come back here to accept it.
        </p>
        <div className="page-actions">
          <Link className="button" to="/login">Sign in</Link>
          <Link className="button button-quiet" to="/register">Create an account</Link>
        </div>
      </>
    );
  } else if (preview.isLoading) {
    body = <p className="muted">Checking the invitation…</p>;
  } else if (preview.isError) {
    body = <p className="alert alert-error">{preview.error.message}</p>;
  } else {
    const invitation = preview.data;
    const wrongEmail = invitation.email !== user.email.toLowerCase();
    body = (
      <>
        <p>
          <strong>{invitation.organisation_name}</strong> has invited{' '}
          <strong>{invitation.email}</strong> to join as{' '}
          <strong>{ROLE_LABELS[invitation.role]}</strong>.
        </p>
        {invitation.state !== 'pending' && (
          <p className="alert alert-error">
            This invitation has been {invitation.state}. Ask for a new one.
          </p>
        )}
        {invitation.state === 'pending' && wrongEmail && (
          <p className="alert alert-warning">
            You are signed in as {user.email}. Sign in with {invitation.email} to accept.
          </p>
        )}
        {accept.isError && <p className="alert alert-error">{accept.error.message}</p>}
        {invitation.state === 'pending' && !wrongEmail && !accepted && (
          <button
            type="button"
            className="button"
            disabled={accept.isPending}
            onClick={() => accept.mutate()}
          >
            {accept.isPending ? 'Joining…' : `Accept and join ${invitation.organisation_name}`}
          </button>
        )}
      </>
    );
  }

  return (
    <div className="app-main">
      <div className="page setup-page">
        <section className="card reveal setup-card">
          <h1>Invitation</h1>
          {body}
        </section>
      </div>
    </div>
  );
}
