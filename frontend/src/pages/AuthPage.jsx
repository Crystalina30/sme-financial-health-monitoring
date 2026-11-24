import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import AuthLayout from '../components/AuthLayout.jsx';
import LoginForm from '../components/LoginForm.jsx';
import RegisterForm from '../components/RegisterForm.jsx';
import { useAuth } from '../context/AuthContext.jsx';

// Serves both /login and /register. Staying mounted across the two routes is
// what lets the panel slide across the card instead of the page reloading.
export default function AuthPage() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [isShaking, setIsShaking] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const mode = pathname === '/register' ? 'register' : 'login';

  return (
    <AuthLayout mode={mode} isShaking={isShaking} onShakeEnd={() => setIsShaking(false)}>
      <LoginForm active={mode === 'login'} onFailure={() => setIsShaking(true)} />
      <RegisterForm active={mode === 'register'} onFailure={() => setIsShaking(true)} />
    </AuthLayout>
  );
}
