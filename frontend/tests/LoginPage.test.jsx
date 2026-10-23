import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import LoginPage from '../src/pages/LoginPage.jsx';

const login = vi.fn();

vi.mock('../src/context/AuthContext.jsx', () => ({
    useAuth: () => ({ user: null, login }),
}));

function renderLogin() {
    return render(
        <MemoryRouter initialEntries={['/login']}>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/companies" element={<p>Companies page</p>} />
            </Routes>
        </MemoryRouter>,
    );
}

function fill(email, password) {
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: email } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
}

afterEach(() => {
    login.mockReset();
});

describe('LoginPage', () => {
    it('shows field messages and does not call login when fields are empty', () => {
        renderLogin();
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

        expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
        expect(screen.getByText('Enter your password.')).toBeInTheDocument();
        expect(login).not.toHaveBeenCalled();
    });

    it('rejects a malformed email address', () => {
        renderLogin();
        fill('not-an-email', 'secret123');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

        expect(screen.getByText(/Enter a valid email address/)).toBeInTheDocument();
        expect(login).not.toHaveBeenCalled();
    });

    it('signs in and redirects to the companies page', async () => {
        login.mockResolvedValue(undefined);
        renderLogin();
        fill('owner@example.com', 'secret123');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

        expect(login).toHaveBeenCalledWith('owner@example.com', 'secret123');
        expect(await screen.findByText('Companies page')).toBeInTheDocument();
    });

    it('shows the server error when credentials are rejected', async () => {
        login.mockRejectedValue(new Error('Incorrect email address or password.'));
        renderLogin();
        fill('owner@example.com', 'wrong-password');
        fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

        expect(await screen.findByRole('alert')).toHaveTextContent(
            'Incorrect email address or password.',
        );
        await waitFor(() =>
            expect(screen.getByRole('button', { name: 'Sign in' })).not.toBeDisabled(),
        );
    });

    it('toggles password visibility', () => {
        renderLogin();
        const password = screen.getByLabelText('Password');
        expect(password).toHaveAttribute('type', 'password');

        fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
        expect(password).toHaveAttribute('type', 'text');

        fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
        expect(password).toHaveAttribute('type', 'password');
    });
});
