'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import AuthLayoutV2 from '@/components/AuthLayoutV2'; // Import AuthLayoutV2
import Link from 'next/link'; // Ensure Link is imported

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const result = await signIn('credentials', {
      redirect: false,
      email: email,
      password: password,
    });

    if (result?.error) {
      setError('Email ou senha inválidos.');
    } else if (result?.ok) {
      router.push('/');
      router.refresh();
    }
  };

  return (
    <AuthLayoutV2
      title="Login"
      subtitle="Enter your account details"
      visualTitle="Bem vindo(a) de volta"
      visualSubtitle="Acesse sua conta para gerenciar suas licitações de forma inteligente e eficiente."
    >
      <form onSubmit={handleSubmit} className="space-y-6"> {/* Removed w-full as it's handled by AuthLayoutV2's inner div */}
        {error && <p className="bg-red-100 text-red-700 p-3 mb-4 rounded text-sm">{error}</p>}
        
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
            className="mt-1 block w-full px-4 py-3 border-b-2 border-gray-300 bg-transparent text-gray-900 focus:outline-none focus:border-licitai-primary"
            placeholder="seu@email.com"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">Password</label>
            <Link href="#" className="font-medium text-licitai-primary hover:text-licitai-secondary">
              Forgot Password?
            </Link>
          </div>
          <input
            type="password"
            id="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full px-4 py-3 border-b-2 border-gray-300 bg-transparent text-gray-900 focus:outline-none focus:border-licitai-primary"
          />
        </div>
        
        <button
          type="submit"
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-licitai-secondary hover:bg-licitai-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-licitai-primary transition-all duration-200"
        >
          Login
        </button>
      </form>
    </AuthLayoutV2>
  );
}
