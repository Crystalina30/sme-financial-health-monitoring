import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { THEME_STORAGE_KEY, ThemeProvider } from '../src/context/ThemeContext.jsx';
import AuthPage from '../src/pages/AuthPage.jsx';

const login = vi.fn();
const register = vi.fn();
let currentUser = null;

vi.mock('../src/context/AuthContext.jsx', () => ({
  useAuth: () => ({ user: currentUser, login, register }),
}));

function renderAt(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AuthPage />}>
            <Route path="/login" element={null} />
            <Route path="/register" element={null} />
          </Route>
          <Route path="/" element={<p>Home page for the role</p>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

// Inactive forms are aria-hidden, so getByRole only finds the one on screen.
const loginForm = () => within(screen.getByRole('form', { name: 'Sign in' }));
const registerForm = () => within(screen.getByRole('form', { name: 'Create an account' }));

function fillLogin(email, password) {
  fireEvent.change(loginForm().getByLabelText('Email address'), { target: { value: email } });
  fireEvent.change(loginForm().getByLabelText('Password'), { target: { value: password } });
}

function fillRegister(fullName, email, password) {
  const form = registerForm();
  fireEvent.change(form.getByLabelText('Full name'), { target: { value: fullName } });
  fireEvent.change(form.getByLabelText('Email address'), { target: { value: email } });
  fireEvent.change(form.getByLabelText('Password'), { target: { value: password } });
}

beforeEach(() => {
  currentUser = null;
  localStorage.removeItem(THEME_STORAGE_KEY);
  delete document.documentElement.dataset.theme;
});

afterEach(() => {
  login.mockReset();
  register.mockReset();
});

describe('sign in', () => {
  it('shows field messages and does not call login when fields are empty', () => {
    renderAt('/login');
    fireEvent.click(loginForm().getByRole('button', { name: 'Sign in' }));

    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('rejects a malformed email address', () => {
    renderAt('/login');
    fillLogin('not-an-email', 'secret123');
    fireEvent.click(loginForm().getByRole('button', { name: 'Sign in' }));

    expect(screen.getByText(/Enter a valid email address/)).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('signs in and redirects to the home page for the role', async () => {
    login.mockResolvedValue(undefined);
    renderAt('/login');
    fillLogin('owner@example.com', 'secret123');
    fireEvent.click(loginForm().getByRole('button', { name: 'Sign in' }));

    expect(login).toHaveBeenCalledWith('owner@example.com', 'secret123');
    expect(await screen.findByText('Home page for the role')).toBeInTheDocument();
  });

  it('shows the server error when credentials are rejected', async () => {
    login.mockRejectedValue(new Error('Incorrect email address or password.'));
    renderAt('/login');
    fillLogin('owner@example.com', 'wrong-password');
    fireEvent.click(loginForm().getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Incorrect email address or password.',
    );
    expect(loginForm().getByRole('button', { name: 'Sign in' })).not.toBeDisabled();
  });

  it('toggles password visibility', () => {
    renderAt('/login');
    const password = loginForm().getByLabelText('Password');
    expect(password).toHaveAttribute('type', 'password');

    fireEvent.click(loginForm().getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');

    fireEvent.click(loginForm().getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  it('redirects an account that is already signed in', () => {
    currentUser = { email: 'owner@example.com' };
    renderAt('/login');

    expect(screen.getByText('Home page for the role')).toBeInTheDocument();
  });
});

describe('create an account', () => {
  it('shows field messages and does not register when fields are empty', () => {
    renderAt('/register');
    fireEvent.click(registerForm().getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Choose a password.')).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it('rejects a password shorter than 8 characters', () => {
    renderAt('/register');
    fillRegister('Ada Owner', 'owner@example.com', 'short');
    fireEvent.click(registerForm().getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it('registers and redirects to the home page for the role', async () => {
    register.mockResolvedValue(undefined);
    renderAt('/register');
    fillRegister('Ada Owner', 'owner@example.com', 'secret123');
    fireEvent.click(registerForm().getByRole('button', { name: 'Create account' }));

    expect(register).toHaveBeenCalledWith('owner@example.com', 'Ada Owner', 'secret123');
    expect(await screen.findByText('Home page for the role')).toBeInTheDocument();
  });

  it('shows the server error when the email is already registered', async () => {
    register.mockRejectedValue(new Error('An account with this email already exists.'));
    renderAt('/register');
    fillRegister('Ada Owner', 'owner@example.com', 'secret123');
    fireEvent.click(registerForm().getByRole('button', { name: 'Create account' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An account with this email already exists.',
    );
  });
});

describe('switching between the two forms', () => {
  it('slides the same panel to the other side and back', () => {
    const { container } = renderAt('/login');
    const panel = container.querySelector('.auth-panel');
    const activeTitle = () => container.querySelector('.auth-panel-content.is-active h2');
    expect(panel).toHaveClass('auth-panel--login');
    expect(activeTitle()).toHaveTextContent('Welcome back');

    fireEvent.click(loginForm().getByRole('link', { name: 'Create one' }));

    // The same element, not a replacement: only a live element can transition.
    expect(container.querySelector('.auth-panel')).toBe(panel);
    expect(panel).toHaveClass('auth-panel--register');
    expect(activeTitle()).toHaveTextContent('Get started');

    fireEvent.click(registerForm().getByRole('link', { name: 'Sign in' }));

    expect(panel).toHaveClass('auth-panel--login');
    expect(activeTitle()).toHaveTextContent('Welcome back');
  });

  it('exposes only the active form and moves focus to its heading', () => {
    renderAt('/login');
    expect(screen.queryByRole('form', { name: 'Create an account' })).not.toBeInTheDocument();

    fireEvent.click(loginForm().getByRole('link', { name: 'Create one' }));

    expect(screen.queryByRole('form', { name: 'Sign in' })).not.toBeInTheDocument();
    expect(registerForm().getByRole('heading', { name: 'Create an account' })).toHaveFocus();
  });

  it('clears the password and errors of the form being left, but keeps the email', () => {
    renderAt('/login');
    fillLogin('owner@example.com', 'secret123');
    fireEvent.change(loginForm().getByLabelText('Email address'), {
      target: { value: 'not-an-email' },
    });
    fireEvent.click(loginForm().getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText(/Enter a valid email address/)).toBeInTheDocument();

    fireEvent.click(loginForm().getByRole('link', { name: 'Create one' }));
    fireEvent.click(registerForm().getByRole('link', { name: 'Sign in' }));

    expect(loginForm().getByLabelText('Password')).toHaveValue('');
    expect(loginForm().getByLabelText('Email address')).toHaveValue('not-an-email');
    expect(screen.queryByText(/Enter a valid email address/)).not.toBeInTheDocument();
  });
});

describe('theme choice', () => {
  const themeOption = (name) =>
    within(screen.getByRole('radiogroup', { name: 'Colour theme' })).getByRole('radio', { name });

  it('starts in the light theme', () => {
    renderAt('/login');

    expect(themeOption('Light')).toHaveAttribute('aria-checked', 'true');
    expect(themeOption('Dark')).toHaveAttribute('aria-checked', 'false');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('switches to dark and saves the choice', () => {
    renderAt('/login');
    fireEvent.click(themeOption('Dark'));

    expect(themeOption('Dark')).toHaveAttribute('aria-checked', 'true');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('opens in the saved theme next time', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    renderAt('/login');

    expect(themeOption('Dark')).toHaveAttribute('aria-checked', 'true');
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  it('ignores an unrecognised saved value and falls back to light', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'purple');
    renderAt('/login');

    expect(themeOption('Light')).toHaveAttribute('aria-checked', 'true');
  });
});
