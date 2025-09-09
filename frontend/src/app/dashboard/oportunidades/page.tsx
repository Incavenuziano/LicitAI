'use client';

import React from 'react';
import OportunidadesTabela from '@/components/OportunidadesTabela';

export default function OportunidadesPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800">Oportunidades de Licitação</h1>
      <p className="mt-2 text-gray-600">
        Explore as licitações mais recentes e encontre a oportunidade certa para você.
      </p>
      <div className="mt-8">
        <OportunidadesTabela />
      </div>
    </div>
  );
}

