import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import RegisterPage from '../src/pages/RegisterPage.jsx';

const register = vi.fn();

vi.mock('../src/context/AuthContext.jsx', () => ({
  useAuth: () => ({ user: null, register }),
}));

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/companies" element={<p>Companies page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function fill(fullName, email, password) {
  fireEvent.change(screen.getByLabelText('Full name'), { target: { value: fullName } });
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
}

afterEach(() => {
  register.mockReset();
});

describe('RegisterPage', () => {
  it('shows field messages and does not register when fields are empty', () => {
    renderRegister();
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Choose a password.')).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it('rejects a password shorter than 8 characters', () => {
    renderRegister();
    fill('Ada Owner', 'owner@example.com', 'short');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it('registers and redirects to the companies page', async () => {
    register.mockResolvedValue(undefined);
    renderRegister();
    fill('Ada Owner', 'owner@example.com', 'secret123');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(register).toHaveBeenCalledWith('owner@example.com', 'Ada Owner', 'secret123');
    expect(await screen.findByText('Companies page')).toBeInTheDocument();
  });

  it('shows the server error when the email is already registered', async () => {
    register.mockRejectedValue(new Error('An account with this email already exists.'));
    renderRegister();
    fill('Ada Owner', 'owner@example.com', 'secret123');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'An account with this email already exists.',
    );
  });
});
