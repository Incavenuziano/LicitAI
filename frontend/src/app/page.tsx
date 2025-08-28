'use client';

import LicitacoesTabela from '@/components/LicitacoesTabela';
import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';
import { useRouter } from 'next/navigation'; // Import useRouter

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter(); // Initialize useRouter

  // Redirect to login if unauthenticated
  if (status === 'unauthenticated') {
    router.push('/login');
    return null; // Or a loading spinner, to prevent flickering
  }

  return (
    <main className="flex min-h-screen flex-col items-center p-8">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-8">
        <h1 className="text-2xl font-bold">LicitAI</h1>
        {status === 'authenticated' && session.user && (
          <div className="flex items-center">
            <span>Bem-vindo, {session.user.nickname || session.user.email}</span>
            <button onClick={() => signOut()} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
              Sair
            </button>
          </div>
        )}
      </div>

      {status === 'loading' && <p>Carregando sessão...</p>}

      {status === 'authenticated' && (
        <div className="w-full">
          <h2 className="text-xl mb-4 font-semibold">Licitações Abertas</h2>
          <LicitacoesTabela />
        </div>
      )}
    </main>
  );
}
