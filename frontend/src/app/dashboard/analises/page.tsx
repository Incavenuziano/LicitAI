'use client';

import React from 'react';
import AnalisesTabela from '@/components/AnalisesTabela';

export default function AnalisesPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800">Análises de Licitações</h1>
      <p className="mt-2 text-gray-600">
        Revise as análises de editais que foram concluídas pela IA.
      </p>
      <div className="mt-8">
        <AnalisesTabela />
      </div>
    </div>
  );
}
