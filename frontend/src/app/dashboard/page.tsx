'use client';

import StatCard from '@/components/StatCard';
import { BriefcaseIcon, DollarSignIcon, MagnifyingGlassIcon } from '@/components/SidebarIcons';

// Conteúdo principal da página do Dashboard
export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800">Dashboard Principal</h1>
      <p className="mt-2 text-gray-600">
        Bem-vindo à sua plataforma de análise de licitações.
      </p>

      {/* Seção de Estatísticas */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard
          title="Total de licitações em aberto"
          value="1,234"
          icon={<BriefcaseIcon className="w-8 h-8" />}
        />
        <StatCard
          title="Total de análises feitas"
          value="56"
          icon={<MagnifyingGlassIcon className="w-8 h-8" />}
        />
        <StatCard
          title="Valor total em aberto"
          value="R$ 15.7M"
          icon={<DollarSignIcon className="w-8 h-8" />}
        />
      </div>

      {/* Seção de Gráficos e Acesso Rápido */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
        
        {/* Coluna de Gráficos */}
        <div className="lg:col-span-3 bg-white p-6 rounded-lg shadow-lg">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Tendências</h2>
          <div className="h-64 bg-gray-200 rounded-md flex items-center justify-center">
            <p className="text-gray-500">(Gráfico de Licitações por Estado - Em breve)</p>
          </div>
        </div>

        {/* Coluna de Acesso Rápido */}
        <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-lg">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Acesso Rápido</h2>
          <div className="space-y-4">
            <div>
              <h3 className="font-semibold text-gray-700">Suas Buscas Salvas</h3>
              <p className="text-sm text-gray-500 mt-1">(Funcionalidade em breve)</p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-700">Última Chamada</h3>
              <p className="text-sm text-gray-500 mt-1">(Licitações que finalizam em 7 dias - Em breve)</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}