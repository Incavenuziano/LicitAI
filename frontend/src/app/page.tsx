'use client';

import LicitacoesTabela from '@/components/LicitacoesTabela';
import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';

export default function Home() {
  const { data: session, status } = useSession();

  return (
    <main className="flex min-h-screen flex-col items-center p-8">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-8">
        <h1 className="text-2xl font-bold">LicitAI</h1>
        {status === 'authenticated' && session.user && (
          <div className="flex items-center">
            <span>Bem-vindo, {session.user.email}</span>
            <button onClick={() => signOut()} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
              Sair
            </button>
          </div>
        )}
      </div>

      {status === 'loading' && <p>Carregando sessão...</p>}

      {status === 'unauthenticated' && (
        <div className="text-center w-full p-12 border rounded-lg">
          <h2 className="text-xl font-semibold mb-4">Acesso Restrito</h2>
          <p className="mb-6">Por favor, faça login para ver as licitações.</p>
          <Link href="/login" className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
            Fazer Login
          </Link>
        </div>
      )}

      {status === 'authenticated' && (
        <div className="w-full">
          <h2 className="text-xl mb-4 font-semibold">Licitações Abertas</h2>
          <LicitacoesTabela />
        </div>
      )}
    </main>
  );
}
