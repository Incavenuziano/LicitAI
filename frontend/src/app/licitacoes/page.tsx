'use client';

import LicitacoesTabela from '@/components/LicitacoesTabela';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';

export default function LicitacoesPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  if (status === 'unauthenticated') {
    router.push('/login');
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-6">
        <h1 className="text-2xl font-bold">Licitações</h1>
        {status === 'authenticated' && session?.user && (
          <button onClick={() => signOut()} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
            Sair
          </button>
        )}
      </div>
      {status === 'loading' && <p>{'Carregando sessão...'}</p>}
      {status === 'authenticated' && (
        <div className="w-full max-w-5xl">
          <LicitacoesTabela />
        </div>
      )}
    </main>
  );
}
