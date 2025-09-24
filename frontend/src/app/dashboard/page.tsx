"use client";

import { useEffect, useState } from "react";
import StatCard from "@/components/StatCard";
import {
  BriefcaseIcon,
  DollarSignIcon,
  MagnifyingGlassIcon,
} from "@/components/SidebarIcons";
import LicitacoesPorUfChart from "@/components/charts/LicitacoesPorUfChart";
import LicitacoesPorUfPie from "@/components/charts/LicitacoesPorUfPie";
import { getAnalisesTotal, getStatsLicitacoesPorUf } from "@/services/api";

export default function DashboardPage() {
  const [totalLicitacoes, setTotalLicitacoes] = useState<string>("Carregando...");
  const [totalAnalises, setTotalAnalises] = useState<string>("Carregando...");

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const [stats, analises] = await Promise.all([
          getStatsLicitacoesPorUf(),
          getAnalisesTotal(),
        ]);

        if (!active) return;

        const totalL = Array.isArray(stats)
          ? stats.reduce((acc, item) => acc + (item.total ?? 0), 0)
          : 0;
        const totalA = Number.isFinite(analises) ? analises : 0;

        setTotalLicitacoes(totalL.toLocaleString("pt-BR"));
        setTotalAnalises(totalA.toLocaleString("pt-BR"));
      } catch (error) {
        console.error("Falha ao carregar estatísticas do dashboard", error);
        if (active) {
          setTotalLicitacoes("—");
          setTotalAnalises("—");
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800">Dashboard Principal</h1>
      <p className="mt-2 text-gray-600">Bem-vindo à sua plataforma de análise de licitações.</p>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard
          title="Total de licitações em aberto"
          value={totalLicitacoes}
          icon={<BriefcaseIcon className="w-8 h-8" />}
        />
        <StatCard
          title="Total de análises feitas"
          value={totalAnalises}
          icon={<MagnifyingGlassIcon className="w-8 h-8" />}
        />
        <StatCard
          title="Valor total em aberto"
          value="R$ 15.7M"
          icon={<DollarSignIcon className="w-8 h-8" />}
        />
      </div>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <LicitacoesPorUfChart />
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <LicitacoesPorUfPie />
          </div>
        </div>

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
