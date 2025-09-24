'use client';

import React, { useState } from 'react';
import OportunidadesTabela from '@/components/OportunidadesTabela';
import OportunidadesAbertas from '@/components/OportunidadesAbertas';

export default function OportunidadesPage() {
  const [tab, setTab] = useState<'banco' | 'abertas'>('banco');
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800">Oportunidades de Licitação</h1>
      <p className="mt-2 text-gray-600">
        Explore as licitações no banco e as propostas em aberto no PNCP.
      </p>
      <div className="mt-6 flex gap-2">
        <button
          onClick={() => setTab('banco')}
          className={`px-4 py-2 rounded ${tab === 'banco' ? 'bg-indigo-600 text-white' : 'bg-gray-200'}`}
        >
          Do Banco
        </button>
        <button
          onClick={() => setTab('abertas')}
          className={`px-4 py-2 rounded ${tab === 'abertas' ? 'bg-indigo-600 text-white' : 'bg-gray-200'}`}
        >
          Em Aberto (PNCP)
        </button>
      </div>
      <div className="mt-8">
        {tab === 'banco' ? <OportunidadesTabela /> : <OportunidadesAbertas />}
      </div>
    </div>
  );
}
