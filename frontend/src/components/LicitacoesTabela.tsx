'use client'; // Indica que este é um Componente de Cliente

import { useEffect, useState, useMemo, useRef } from 'react';
import { getLicitacoes } from '@/services/api';
import { Licitacao } from '@/types';

// --- LÓGICA DE CLASSIFICAÇÃO ---
const getClassificacao = (objeto: string | null): string => {
  if (!objeto) return 'Outros';
  const texto = objeto.toLowerCase();
  const keywordsServico = ["serviços", "consultoria", "manutenção", "execução de obra", "elaboração de projeto"];
  const keywordsAquisicao = ["aquisição", "compra", "fornecimento", "material", "equipamentos"];
  if (keywordsServico.some(kw => texto.includes(kw))) return 'Serviço';
  if (keywordsAquisicao.some(kw => texto.includes(kw))) return 'Aquisição';
  return 'Outros';
};

export default function LicitacoesTabela() {
  const [licitacoes, setLicitacoes] = useState<Licitacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroUF, setFiltroUF] = useState('');
  const [ordemValor, setOrdemValor] = useState('');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');
  const [filtroTipo, setFiltroTipo] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const selectAllCheckboxRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const data = await getLicitacoes();
      setLicitacoes(data);
      setLoading(false);
    };
    fetchData();
  }, []);

  const licitacoesExibidas = useMemo(() => {
    let licitacoesProcessadas = [...licitacoes];
    if (filtroUF) { licitacoesProcessadas = licitacoesProcessadas.filter((l) => l.uf === filtroUF); }
    if (dataInicio) { const inicio = new Date(dataInicio + 'T00:00:00'); licitacoesProcessadas = licitacoesProcessadas.filter((l) => l.data_encerramento_proposta && new Date(l.data_encerramento_proposta) >= inicio); }
    if (dataFim) { const fim = new Date(dataFim + 'T23:59:59'); licitacoesProcessadas = licitacoesProcessadas.filter((l) => l.data_encerramento_proposta && new Date(l.data_encerramento_proposta) <= fim); }
    if (filtroTipo) { licitacoesProcessadas = licitacoesProcessadas.filter((l) => getClassificacao(l.objeto_compra) === filtroTipo); }
    if (ordemValor) { licitacoesProcessadas.sort((a, b) => { const vA = a.valor_total_estimado ? parseFloat(a.valor_total_estimado) : 0; const vB = b.valor_total_estimado ? parseFloat(b.valor_total_estimado) : 0; return ordemValor === 'asc' ? vA - vB : vB - vA; }); }
    return licitacoesProcessadas;
  }, [licitacoes, filtroUF, ordemValor, dataInicio, dataFim, filtroTipo]);

  const ufsDisponiveis = useMemo(() => 
    [...new Set(licitacoes.map((l) => l.uf).filter(Boolean))].sort()
  , [licitacoes]);

  const handleSelect = (id: number) => {
    const newSelectedIds = new Set(selectedIds);
    if (newSelectedIds.has(id)) newSelectedIds.delete(id); else newSelectedIds.add(id);
    setSelectedIds(newSelectedIds);
  };

  const handleSelectAll = () => {
    if (selectedIds.size === licitacoesExibidas.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(licitacoesExibidas.map(l => l.id)));
    }
  };

  // --- LÓGICA DE EXPORTAÇÃO ---
  const handleExport = () => {
    if (selectedIds.size === 0) return;
    const dataToExport = licitacoes.filter(l => selectedIds.has(l.id));
    const headers = ["id", "numero_controle_pncp", "objeto_compra", "valor_total_estimado", "orgao_entidade_nome", "uf", "municipio_nome", "data_publicacao_pncp", "data_encerramento_proposta", "link_sistema_origem"];
    
    const sanitizeCell = (cellData: any) => {
      if (cellData === null || cellData === undefined) return '';
      const str = String(cellData);
      const escapedStr = str.replace(/"/g, '""');
      return `"${escapedStr}"`;
    };

    const csvRows = [headers.join(',')];
    dataToExport.forEach(item => {
      const row = headers.map(header => sanitizeCell(item[header as keyof Licitacao]));
      csvRows.push(row.join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'licitacoes_selecionadas.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    const isIndeterminate = selectedIds.size > 0 && selectedIds.size < licitacoesExibidas.length;
    if (selectAllCheckboxRef.current) {
      selectAllCheckboxRef.current.indeterminate = isIndeterminate;
    }
  }, [selectedIds, licitacoesExibidas]);

  if (loading) return <p>Carregando licitações...</p>;

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Licitações Encontradas</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4 p-4 bg-gray-50 rounded-lg border">
        {/* ... (filtros) ... */}
        <div><label htmlFor="filtro-uf" className="block text-sm font-medium text-gray-700 mb-1">Estado (UF)</label><select id="filtro-uf" value={filtroUF} onChange={(e) => setFiltroUF(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"><option value="">Todos</option>{ufsDisponiveis.map((uf) => (<option key={uf} value={uf}>{uf}</option>))}</select></div>
        <div><label htmlFor="filtro-tipo" className="block text-sm font-medium text-gray-700 mb-1">Tipo de Licitação</label><select id="filtro-tipo" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"><option value="">Todos</option><option value="Serviço">Serviço</option><option value="Aquisição">Aquisição</option><option value="Outros">Outros</option></select></div>
        <div><label className="block text-sm font-medium text-gray-700 mb-1">Encerramento Entre</label><div className="flex items-center gap-2"><input type="date" value={dataInicio} onChange={(e) => setDataInicio(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"/><input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} className="w-full p-2 border border-gray-300 rounded-md shadow-sm"/></div></div>
        <div><label className="block text-sm font-medium text-gray-700 mb-1">Ações</label><div className="flex gap-2"><button onClick={() => setOrdemValor('asc')} className={`flex-1 p-2 text-sm rounded-md ${ordemValor === 'asc' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}>Valor Crescente</button><button onClick={() => setOrdemValor('desc')} className={`flex-1 p-2 text-sm rounded-md ${ordemValor === 'desc' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}>Valor Decrescente</button><button onClick={() => { setOrdemValor(''); setFiltroUF(''); setDataInicio(''); setDataFim(''); setFiltroTipo(''); setSelectedIds(new Set()); }} className="p-2 text-sm bg-gray-300 rounded-md">Limpar</button></div></div>
      </div>

      <div className="flex items-center justify-between mb-2 h-9">
        <div className="text-sm text-gray-600">
          {selectedIds.size > 0 && <span>{selectedIds.size} de {licitacoesExibidas.length} itens selecionados.</span>}
        </div>
        {selectedIds.size > 0 && (
          <button onClick={handleExport} className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:bg-gray-400" disabled={selectedIds.size === 0}>
            Exportar Selecionados (CSV)
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-200">
          <thead>
            <tr className="bg-gray-100">
              <th className="py-2 px-3 border-b w-12 text-center"><input type="checkbox" ref={selectAllCheckboxRef} checked={licitacoesExibidas.length > 0 && selectedIds.size === licitacoesExibidas.length} onChange={handleSelectAll} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" /></th>
              <th className="py-2 px-4 border-b">Órgão</th>
              <th className="py-2 px-4 border-b">Objeto</th>
              <th className="py-2 px-4 border-b">Data de Encerramento</th>
              <th className="py-2 px-4 border-b">Valor Estimado</th>
              <th className="py-2 px-4 border-b">Edital</th>
            </tr>
          </thead>
          <tbody>
            {licitacoesExibidas.map((licitacao) => (
              <tr key={licitacao.id} className={`${selectedIds.has(licitacao.id) ? 'bg-blue-100' : 'hover:bg-gray-50'}`}>
                <td className="py-2 px-3 border-b text-center"><input type="checkbox" checked={selectedIds.has(licitacao.id)} onChange={() => handleSelect(licitacao.id)} className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" /></td>
                <td className="py-2 px-4 border-b">{licitacao.orgao_entidade_nome}</td>
                <td className="py-2 px-4 border-b">{licitacao.objeto_compra}</td>
                <td className="py-2 px-4 border-b">{licitacao.data_encerramento_proposta ? new Date(licitacao.data_encerramento_proposta).toLocaleDateString('pt-BR') : 'N/A'}</td>
                <td className="py-2 px-4 border-b text-right">{licitacao.valor_total_estimado ? parseFloat(licitacao.valor_total_estimado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : 'N/A'}</td>
                <td className="py-2 px-4 border-b text-center">{licitacao.link_sistema_origem ? (<a href={licitacao.link_sistema_origem} target="_blank" rel="noopener noreferrer" className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded text-sm">Acessar</a>) : ('N/D')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}