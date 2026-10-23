import { useState } from 'react';

const ICON_PATHS = {
  user: (
    <>
      <circle cx="12" cy="8" r="3.75" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </>
  ),
  lock: (
    <>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </>
  ),
};

function Icon({ name }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {ICON_PATHS[name]}
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

/**
 * Check every named input in the form against its own constraints
 * (required, type="email", minLength) and return { name: message } for the
 * ones that fail. `messages` only supplies the wording; the browser's rules
 * still decide what is valid.
 */
export function collectFieldErrors(form, messages) {
  const errors = {};
  for (const input of form.querySelectorAll('input[name]')) {
    const wording = messages[input.name] || {};
    // minLength is checked by hand: browsers only flag tooShort after the
    // user has typed, not for a value set any other way.
    const tooShort = input.minLength > 0 && input.value.length > 0 && input.value.length < input.minLength;
    if (input.checkValidity() && !tooShort) continue;
    if (input.validity.valueMissing) errors[input.name] = wording.valueMissing;
    else if (input.validity.typeMismatch) errors[input.name] = wording.typeMismatch;
    else if (tooShort) errors[input.name] = wording.tooShort;
    else errors[input.name] = input.validationMessage;
  }
  return errors;
}

/**
 * One input on the sign-in or registration card: icon, animated focus
 * border, optional show/hide toggle for passwords, and its error or hint.
 * The label is visually hidden but still read by screen readers.
 */
export default function AuthField({
  id,
  label,
  icon,
  type = 'text',
  error,
  hint,
  revealable = false,
  index = 0,
  onChange,
  ...inputProps
}) {
  const [revealed, setRevealed] = useState(false);
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  return (
    <div className="auth-field auth-reveal" style={{ '--i': index }}>
      <label htmlFor={id} className="auth-sr-only">
        {label}
      </label>
      <div className={`auth-control${error ? ' is-invalid' : ''}`}>
        <div className="auth-control-inner">
          <span className="auth-icon">
            <Icon name={icon} />
          </span>
          <input
            id={id}
            name={id}
            type={revealable && revealed ? 'text' : type}
            className={`auth-input${revealable ? ' auth-input--with-toggle' : ''}`}
            placeholder={label}
            onChange={(event) => onChange(event.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            {...inputProps}
          />
          {revealable && (
            <button
              type="button"
              className="auth-toggle"
              onClick={() => setRevealed((shown) => !shown)}
              aria-label={revealed ? 'Hide password' : 'Show password'}
              aria-controls={id}
            >
              <EyeIcon crossed={revealed} />
            </button>
          )}
        </div>
      </div>
      {error ? (
        <p id={`${id}-error`} className="auth-field-error">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="auth-field-hint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
