"use client"; // Indica que este é um Componente de Cliente

import { useEffect, useState, useMemo } from 'react';
import { getLicitacoes } from '@/services/api';
import { Licitacao } from '@/types';

export default function LicitacoesTabela() {
  // Estados para os dados e UI
  const [licitacoes, setLicitacoes] = useState<Licitacao[]>([]);
  const [loading, setLoading] = useState(true);

  // --- ESTADOS PARA FILTRO E ORDENAÇÃO ---
  const [filtroUF, setFiltroUF] = useState('');
  const [ordemValor, setOrdemValor] = useState(''); // 'asc', 'desc', ou ''
  const [dataInicio, setDataInicio] = useState(''); // YYYY-MM-DD
  const [dataFim, setDataFim] = useState('');       // YYYY-MM-DD

  // Busca os dados da API
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const data = await getLicitacoes();
      setLicitacoes(data);
      setLoading(false);
    };

    fetchData();
  }, []);

  // --- LÓGICA PARA FILTRAR E ORDENAR ---
  const licitacoesExibidas = useMemo(() => {
    let licitacoesProcessadas = [...licitacoes];

    // 1. Filtro de UF
    if (filtroUF) {
      licitacoesProcessadas = licitacoesProcessadas.filter((l) => l.uf === filtroUF);
    }

    // 2. Filtro por intervalo de datas
    if (dataInicio) {
      const inicio = new Date(dataInicio + 'T00:00:00'); // Adiciona tempo para evitar problemas de fuso
      licitacoesProcessadas = licitacoesProcessadas.filter((l) => {
        if (!l.data_encerramento_proposta) return false;
        return new Date(l.data_encerramento_proposta) >= inicio;
      });
    }
    if (dataFim) {
      const fim = new Date(dataFim + 'T23:59:59'); // Considera até o final do dia
      licitacoesProcessadas = licitacoesProcessadas.filter((l) => {
        if (!l.data_encerramento_proposta) return false;
        return new Date(l.data_encerramento_proposta) <= fim;
      });
    }

    // 3. Ordenação por valor
    if (ordemValor) {
      licitacoesProcessadas.sort((a, b) => {
        const valorA = a.valor_total_estimado ? parseFloat(a.valor_total_estimado) : 0;
        const valorB = b.valor_total_estimado ? parseFloat(b.valor_total_estimado) : 0;
        return ordemValor === 'asc' ? valorA - valorB : valorB - valorA;
      });
    }

    return licitacoesProcessadas;
  }, [licitacoes, filtroUF, ordemValor, dataInicio, dataFim]);

  // Extrai as UFs únicas para popular o dropdown do filtro
  const ufsDisponiveis = useMemo(() => 
    [...new Set(licitacoes.map((l) => l.uf).filter(Boolean))].sort()
  , [licitacoes]);


  if (loading) {
    return <p>Carregando licitações...</p>;
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Licitações Encontradas</h1>

      {/* --- CONTROLES DE FILTRO E ORDENAÇÃO --- */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 p-4 bg-gray-50 rounded-lg border">
        {/* Filtro de UF */}
        <div className="">
          <label htmlFor="filtro-uf" className="block text-sm font-medium text-gray-700 mb-1">Estado (UF)</label>
          <select id="filtro-uf" value={filtroUF} onChange={(e) => setFiltroUF(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
            <option value="">Todos</option>
            {ufsDisponiveis.map((uf) => (<option key={uf} value={uf}>{uf}</option>))}
          </select>
        </div>

        {/* Filtro de Data */}
        <div className="">
            <label className="block text-sm font-medium text-gray-700 mb-1">Encerramento Entre</label>
            <div className="flex items-center gap-2">
                <input type="date" value={dataInicio} onChange={(e) => setDataInicio(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"/>
                <span>até</span>
                <input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"/>
            </div>
        </div>

        {/* Ordenação por Valor */}
        <div className="">
          <label className="block text-sm font-medium text-gray-700 mb-1">Ordenar por Valor</label>
          <div className="flex gap-2">
            <button onClick={() => setOrdemValor('asc')} className={`w-full p-2 text-sm rounded-md ${ordemValor === 'asc' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}>Menor</button>
            <button onClick={() => setOrdemValor('desc')} className={`w-full p-2 text-sm rounded-md ${ordemValor === 'desc' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}>Maior</button>
            <button onClick={() => { setOrdemValor(''); setFiltroUF(''); setDataInicio(''); setDataFim(''); }} className="p-2 text-sm bg-gray-300 rounded-md">Limpar Filtros</button>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-200">
          <thead>
            <tr className="bg-gray-100">
              <th className="py-2 px-4 border-b">Órgão</th>
              <th className="py-2 px-4 border-b">Objeto</th>
              <th className="py-2 px-4 border-b">Data de Encerramento</th>
              <th className="py-2 px-4 border-b">Valor Estimado</th>
              <th className="py-2 px-4 border-b">Edital</th>
            </tr>
          </thead>
          <tbody>
            {licitacoesExibidas.map((licitacao) => (
              <tr key={licitacao.id} className="hover:bg-gray-50">
                <td className="py-2 px-4 border-b">{licitacao.orgao_entidade_nome}</td>
                <td className="py-2 px-4 border-b">{licitacao.objeto_compra}</td>
                <td className="py-2 px-4 border-b">
                  {licitacao.data_encerramento_proposta ? new Date(licitacao.data_encerramento_proposta).toLocaleDateString('pt-BR') : 'N/A'}
                </td>
                <td className="py-2 px-4 border-b text-right">
                  {licitacao.valor_total_estimado ? parseFloat(licitacao.valor_total_estimado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : 'N/A'}
                </td>
                <td className="py-2 px-4 border-b text-center">
                  {licitacao.link_sistema_origem ? (
                    <a href={licitacao.link_sistema_origem} target="_blank" rel="noopener noreferrer" className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded text-sm">
                      Acessar
                    </a>
                  ) : (
                    'N/D'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
