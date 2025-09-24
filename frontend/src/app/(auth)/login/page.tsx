'use client';

import type { NextPage } from 'next';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { signIn } from 'next-auth/react';
import styles from './login.module.css';
import LogoBranca from '@/components/LogoBranca';

const LoginContent: NextPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError('');
    setSubmitting(true);
    try {
      const result = await signIn('credentials', {
        redirect: false,
        email,
        password,
      });
      if (result?.error) {
        setError('Email ou senha inválidos.');
      } else if (result?.ok) {
        router.push('/');
        router.refresh();
      }
    } catch (e) {
      setError('Falha ao conectar. Tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const code = searchParams.get('error');
    if (!code) return;
    const map: Record<string, string> = {
      CredentialsSignin: 'Email ou senha inválidos.',
      AccessDenied: 'Acesso negado.',
      Configuration: 'Erro de configuração do login.',
      default: 'Falha ao autenticar. Tente novamente.',
    };
    setError(map[code] || map.default);
  }, [searchParams]);

  return (
    <div className={styles.container}>
      <div className={styles.leftPanel}>
        <div className={styles.loginForm}>
          <div className={styles.title}>Login</div>
          <div className={styles.subtitle}>Enter your account details</div>

          {error && <p className={styles.error}>{error}</p>}

          <form onSubmit={handleSubmit}>
            <div className={styles.inputGroup}>
              <label htmlFor="email" className={styles.label}>Email:</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={styles.input}
              />
            </div>

            <div className={styles.inputGroup}>
              <label htmlFor="password" className={styles.label}>Password:</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className={styles.input}
              />
            </div>

            <a href="#" className={styles.forgotPassword}>Forget your password?</a>

            <button type="submit" disabled={submitting} className={styles.loginButton}>
              {submitting ? 'Entrando...' : 'Login'}
            </button>
          </form>
        </div>
      </div>
      <div className={styles.rightPanel}>
        <div className={styles.welcomeText}>Bem vindo(a) de volta</div>
        <LogoBranca className={styles.logo} />
      </div>
    </div>
  );
};

const LoginPage: NextPage = () => (
  <Suspense fallback={<div className={styles.container}>Carregando...</div>}>
    <LoginContent />
  </Suspense>
);

export default LoginPage;
