'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useSession, signOut } from 'next-auth/react';

export default function PrecosIndexPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [id, setId] = useState<string>('');
  const [fonte, setFonte] = useState<'comprasgov'|'pncp'|'ambas'>('comprasgov');

  if (status === 'unauthenticated') {
    router.push('/login');
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-6">
        <h1 className="text-2xl font-bold">Preços</h1>
        {status === 'authenticated' && session?.user && (
          <button onClick={() => signOut()} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
            Sair
          </button>
        )}
      </div>

      <div className="w-full max-w-5xl space-y-3">
        <p className="text-gray-600">Consulte preços vencedores por licitação.</p>
        <div className="flex items-center gap-2">
          <input
            value={id}
            onChange={(e) => setId(e.target.value)}
            type="number"
            placeholder="ID da licitação"
            className="border rounded px-3 py-2 w-48"
          />
          <select value={fonte} onChange={(e) => setFonte(e.target.value as any)} className="border rounded px-2 py-2">
            <option value="comprasgov">ComprasGov</option>
            <option value="pncp">PNCP</option>
            <option value="ambas">Ambas</option>
          </select>
          <button
            onClick={() => { if (id) router.push(`/precos/${id}?fonte=${fonte}`); }}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded disabled:bg-gray-400"
            disabled={!id}
          >
            Abrir
          </button>
        </div>
      </div>
    </main>
  );
}
