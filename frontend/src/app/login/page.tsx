'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

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

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-licitai-bg-light">
      {/* Painel visual / branding */}
      <div className="relative hidden md:flex items-center justify-center bg-licitai-visual-bg overflow-hidden">
        <div className="absolute inset-0 opacity-40">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" className="absolute top-0 left-0 w-full h-full">
            <path fill="#C0EEDD" fillOpacity="1" d="M0,192L48,181.3C96,171,192,149,288,138.7C384,128,480,128,576,149.3C672,171,768,213,864,229.3C960,245,1056,235,1152,213.3C1248,192,1344,160,1392,144L1440,128L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
            <path fill="#A0E0C0" fillOpacity="1" d="M0,32L48,53.3C96,75,192,117,288,144C384,171,480,181,576,176C672,171,768,149,864,133.3C960,117,1056,107,1152,112C1248,117,1344,139,1392,149.3L1440,160L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z" />
          </svg>
        </div>
        <div className="relative z-10 max-w-md text-center px-8">
          <div className="w-28 h-28 mx-auto mb-6">
            <Image src="/logo_licitai.png" alt="LicitAI" width={112} height={112} className="w-full h-full object-contain" />
          </div>
          <h1 className="text-4xl font-bold text-licitai-primary mb-3">LicitAI</h1>
          <p className="text-licitai-secondary">Acesse sua conta para gerenciar licitações com inteligência.</p>
        </div>
      </div>

      {/* Formulário */}
      <div className="flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 md:hidden">
            <Image src="/logo_licitai.png" alt="LicitAI" width={36} height={36} className="w-9 h-9 object-contain" />
            <span className="text-xl font-semibold text-licitai-primary">LicitAI</span>
          </div>
          <div className="rounded-xl border bg-white/90 shadow-xl backdrop-blur p-6 md:p-8">
            <h2 className="text-2xl font-bold text-licitai-primary">Entrar</h2>
            <p className="text-sm text-gray-500 mb-6">Use seu e-mail e senha para continuar.</p>

            {error && (
              <div className="mb-4 rounded border border-red-200 bg-red-50 text-red-700 px-3 py-2 text-sm" role="alert">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="seu@email.com"
                  className={`mt-1 block w-full rounded-md border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-licitai-primary/40 focus:border-licitai-primary/60 ${error ? 'border-red-300' : 'border-gray-300'}`}
                  aria-invalid={!!error}
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700">Senha</label>
                <div className={`mt-1 flex items-center rounded-md border ${error ? 'border-red-300' : 'border-gray-300'} focus-within:ring-2 focus-within:ring-licitai-primary/40 focus-within:border-licitai-primary/60`}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    name="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-transparent px-3 py-2 outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="px-3 py-2 text-gray-500 hover:text-gray-700"
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showPassword ? (
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M3.53 2.47a.75.75 0 10-1.06 1.06l18 18a.75.75 0 101.06-1.06l-2.427-2.427A11.543 11.543 0 0021.75 12C20.94 9.27 17.182 4.5 12 4.5a9.42 9.42 0 00-3.593.695L3.53 2.47zM12 6c4.098 0 7.28 3.38 8.25 6-.248.65-.638 1.42-1.152 2.195L16.28 11.38A4.5 4.5 0 0012.62 7.72L10.9 6.001C11.258 5.967 11.627 6 12 6z"/><path d="M8.53 9.03a4.5 4.5 0 005.94 5.94l-1.153-1.153a3 3 0 01-3.634-3.634L8.53 9.03z"/><path d="M3.75 12c.779-2.436 3.634-5.25 6.902-5.45l-1.39-1.39C6.873 6.142 4.633 8.212 3.75 12z"/></svg>
                    ) : (
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M12 4.5c-5.182 0-8.94 4.77-9.75 7.5.81 2.73 4.568 7.5 9.75 7.5s8.94-4.77 9.75-7.5c-.81-2.73-4.568-7.5-9.75-7.5zm0 3a4.5 4.5 0 110 9 4.5 4.5 0 010-9z"/></svg>
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-licitai-primary focus:ring-licitai-primary" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
                  Lembrar de mim
                </label>
                <a href="#" className="text-sm text-licitai-secondary hover:underline">Esqueci minha senha</a>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-md text-white bg-licitai-secondary hover:bg-licitai-primary transition-colors disabled:opacity-60"
              >
                {submitting ? (
                  <span className="inline-flex items-center gap-2"><span className="h-4 w-4 border-2 border-white/60 border-t-transparent rounded-full animate-spin" /> Entrando...</span>
                ) : (
                  'Entrar'
                )}
              </button>
            </form>

            <div className="mt-6 text-center text-sm text-gray-600">
              Não tem uma conta? <a href="#" className="text-licitai-secondary hover:underline">Cadastre-se</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

