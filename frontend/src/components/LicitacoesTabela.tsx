'use client';

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getLicitacoes, LicitacaoFilters, requestAnalises, buscarLicitacoes, ragIndexar, ragPerguntar } from "@/services/api";
import { Licitacao, Analise } from "@/types";

const UFS_BR = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
  "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
  "RS", "RO", "RR", "SC", "SP", "SE", "TO",
] as const;

const StatusAnalise: React.FC <{
  analise: Analise | undefined;
  onVerResultado: () => void;
}> = ({ analise, onVerResultado }) => {
  if (!analise) {
    return (
      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
        N/A
      </span>
    );
  }
  const getStatusStyle = (status: string) => {
    switch (status) {
      case "Pendente":
      case "Processando":
        return "bg-yellow-100 text-yellow-800";
      case "Em Andamento":
        return "bg-blue-100 text-blue-800";
      case "Concluído":
      case "Concluido":
        return "bg-green-100 text-green-800";
      case "Erro":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };
  return (
    <div className="flex flex-col items-center gap-1">
      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusStyle(analise.status)}`}>
        {analise.status}
      </span>
      {(analise.status === "Concluído" || analise.status === "Concluido") && (
        <button onClick={onVerResultado} className="text-xs text-blue-600 hover:underline">
          Ver Resultado
        </button>
      )}
    </div>
  );
};

const getClassificacao = (objeto: string | null): string => {
  if (!objeto) return "Outros";
  const strip = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  const texto = strip(objeto.toLowerCase());
  const keywordsServico = [
    "servicos",
    "consultoria",
    "manutencao",
    "execucao de obra",
    "elaboracao de projeto",
  ];
  const keywordsAquisicao = [
    "aquisicao",
    "compra",
    "fornecimento",
    "material",
    "equipamentos",
  ];
  if (keywordsServico.some((kw) => texto.includes(kw))) return "Serviço";
  if (keywordsAquisicao.some((kw) => texto.includes(kw))) return "Aquisição";
  return "Outros";
};

export default function LicitacoesTabela() {
  const router = useRouter();
  const [licitacoes, setLicitacoes] = useState<Licitacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroQ, setFiltroQ] = useState("");
  const [filtroUF, setFiltroUF] = useState("");
  const [ordemValor, setOrdemValor] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [filtroTipo, setFiltroTipo] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isAnalysing, setIsAnalysing] = useState(false);
  const [selectedAnalise, setSelectedAnalise] = useState<
    { resultado: string; orgao?: string | null; numero?: string | null; id?: number } | null
  >(null);
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragLoading, setRagLoading] = useState(false);
  const [ragIndexing, setRagIndexing] = useState(false);
  const [ragAnswers, setRagAnswers] = useState<{ q: string; a: string }[]>([]);
  const [isFetchingNew, setIsFetchingNew] = useState(false);
  const selectAllCheckboxRef = useRef<HTMLInputElement | null>(null);

  const fetchData = async (filters: LicitacaoFilters) => {
    setLoading(true);
    const data = await getLicitacoes(filters);
    setLicitacoes(data);
    setLoading(false);
  };

  useEffect(() => {
    const debounceHandler = setTimeout(() => {
      fetchData({ q: filtroQ, uf: filtroUF });
    }, 500); // 500ms delay

    return () => {
      clearTimeout(debounceHandler);
    };
  }, [filtroQ, filtroUF]);

  useEffect(() => {
    const temAnalisePendente = licitacoes.some(
      (l) => l.analises && l.analises.some((a) => ["Pendente", "Em Andamento", "Processando"].includes(a.status))
    );
    if (temAnalisePendente) {
      const timer = setTimeout(() => fetchData({ q: filtroQ, uf: filtroUF }), 5000);
      return () => clearTimeout(timer);
    }
  }, [licitacoes, filtroQ, filtroUF]);

  const licitacoesExibidas = useMemo(() => {
    let licitacoesProcessadas = [...licitacoes];
    // Filtro por tipo e data permanecem no client-side por enquanto.
    if (dataInicio) {
      const inicio = new Date(dataInicio + "T00:00:00");
      licitacoesProcessadas = licitacoesProcessadas.filter(
        (l) => l.data_encerramento_proposta && new Date(l.data_encerramento_proposta) >= inicio
      );
    }
    if (dataFim) {
      const fim = new Date(dataFim + "T23:59:59");
      licitacoesProcessadas = licitacoesProcessadas.filter(
        (l) => l.data_encerramento_proposta && new Date(l.data_encerramento_proposta) <= fim
      );
    }
    if (filtroTipo) {
      licitacoesProcessadas = licitacoesProcessadas.filter(
        (l) => getClassificacao(l.objeto_compra) === filtroTipo
      );
    }
    if (ordemValor) {
      licitacoesProcessadas.sort((a, b) => {
        const vA = a.valor_total_estimado ? parseFloat(a.valor_total_estimado) : 0;
        const vB = b.valor_total_estimado ? parseFloat(b.valor_total_estimado) : 0;
        return ordemValor === "asc" ? vA - vB : vB - vA;
      });
    }
    return licitacoesProcessadas;
  }, [licitacoes, ordemValor, dataInicio, dataFim, filtroTipo]);

  const ufsDisponiveis = UFS_BR as readonly string[];

  const handleSelect = (id: number) => {
    const newSelectedIds = new Set(selectedIds);
    if (newSelectedIds.has(id)) newSelectedIds.delete(id);
    else newSelectedIds.add(id);
    setSelectedIds(newSelectedIds);
  };

  const handleBuscarNovas = async () => {
    try {
      setIsFetchingNew(true);
      await buscarLicitacoes({
        uf: filtroUF || undefined,
        data_inicio: dataInicio || undefined,
        data_fim: dataFim || undefined,
      });
      alert("Busca de novas licitações solicitada. A lista será atualizada.");
      setTimeout(() => fetchData({ q: filtroQ, uf: filtroUF }), 1000);
    } catch (e) {
      console.error(e);
      alert("Erro ao buscar novas licitações.");
    } finally {
      setIsFetchingNew(false);
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.size === licitacoesExibidas.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(licitacoesExibidas.map((l) => l.id)));
    }
  };

  const handleAnalisar = async () => {
    if (selectedIds.size === 0) return;
    setIsAnalysing(true);
    const licitacaoIds = Array.from(selectedIds);
    try {
      await requestAnalises(licitacaoIds);
      setSelectedIds(new Set());
      alert(`${licitacaoIds.length} análise(s) solicitada(s) com sucesso!`);
      setTimeout(() => fetchData({ q: filtroQ, uf: filtroUF }), 1000);
    } catch (error) {
      console.error("Erro ao solicitar análises:", error);
      alert("Ocorreu um erro ao solicitar as análises. Tente novamente.");
    } finally {
      setIsAnalysing(false);
    }
  };

  const handleShowResultado = (licitacao: Licitacao) => {
    const analise = licitacao.analises && licitacao.analises[0];
    if (analise && analise.resultado) {
      setSelectedAnalise({
        resultado: analise.resultado,
        orgao: licitacao.orgao_entidade_nome,
        numero: licitacao.numero_controle_pncp,
        id: licitacao.id,
      });
    } else {
      alert("Não foi possível carregar o resultado da análise.");
    }
  };

  const handleRagAsk = async () => {
    if (!selectedAnalise?.id || !ragQuestion.trim()) return;
    setRagLoading(true);
    try {
      const r = await ragPerguntar(selectedAnalise.id, ragQuestion, 4);
      const answer = (r.results && r.results.length > 0)
        ? r.results.map((x) => x.chunk).join("\n\n---\n\n")
        : 'Nenhum trecho encontrado. Dica: clique em "Indexar" antes e tente novamente.';
      setRagAnswers((prev) => [{ q: ragQuestion, a: answer }, ...prev]);
      setRagQuestion("");
    } catch (e: any) {
      alert(e?.message || "Falha ao consultar o edital");
    } finally {
      setRagLoading(false);
    }
  };

  const handleExport = () => {
    if (selectedIds.size === 0) return;
    const dataToExport = licitacoes.filter((l) => selectedIds.has(l.id));
    const headers = [
      "id",
      "numero_controle_pncp",
      "objeto_compra",
      "valor_total_estimado",
      "orgao_entidade_nome",
      "uf",
      "municipio_nome",
      "data_publicacao_pncp",
      "data_encerramento_proposta",
      "link_sistema_origem",
    ];
    const sanitizeCell = (cellData: any) => {
      if (cellData === null || cellData === undefined) return "";
      const str = String(cellData);
      const escapedStr = str.replace(/\"/g, '""');
      return `"${escapedStr}"`;
    };
    const csvRows = [headers.join(",")];
    dataToExport.forEach((item) => {
      const row = headers.map((header) => sanitizeCell((item as any)[header]));
      csvRows.push(row.join(","));
    });
    const csvString = csvRows.join("\n");
    const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "licitacoes_selecionadas.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    const isIndeterminate =
      selectedIds.size > 0 && selectedIds.size < licitacoesExibidas.length;
    if (selectAllCheckboxRef.current) {
      selectAllCheckboxRef.current.indeterminate = isIndeterminate;
    }
  }, [selectedIds, licitacoesExibidas]);

  if (loading) return <p>{"Carregando licitações..."}</p>;

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">{"Licitações Encontradas"}</h1>

      {/* Filtros */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-4 p-4 bg-gray-50 rounded-lg border">
        <div className="lg:col-span-2">
          <label htmlFor="filtro-q" className="block text-sm font-medium text-gray-700 mb-1">
            Buscar no Objeto
          </label>
          <input
            id="filtro-q"
            type="text"
            value={filtroQ}
            onChange={(e) => setFiltroQ(e.target.value)}
            placeholder="Ex: software, consultoria, etc..."
            className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
          />
        </div>
        <div>
          <label htmlFor="filtro-uf" className="block text-sm font-medium text-gray-700 mb-1">
            Estado (UF)
          </label>
          <select
            id="filtro-uf"
            value={filtroUF}
            onChange={(e) => setFiltroUF(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
          >
            <option value="">Todos</option>
            {ufsDisponiveis.map((uf) => (
              <option key={uf} value={uf}>
                {uf}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filtro-tipo" className="block text-sm font-medium text-gray-700 mb-1">
            {"Tipo de Licitação"}
          </label>
          <select
            id="filtro-tipo"
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
          >
            <option value="">Todos</option>
            <option value="Serviço">{"Serviço"}</option>
            <option value="Aquisição">{"Aquisição"}</option>
            <option value="Outros">Outros</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {"Ações"}
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setFiltroQ("");
                setFiltroUF("");
                setFiltroTipo("");
                setDataInicio("");
                setDataFim("");
                setOrdemValor("");
              }}
              className="flex-1 p-2 text-sm bg-gray-300 rounded-md"
            >
              Limpar Filtros
            </button>
            <button
              onClick={handleBuscarNovas}
              className="flex-1 p-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:bg-gray-400"
              disabled={isFetchingNew}
            >
              {isFetchingNew ? "Buscando..." : "Buscar Novas"}
            </button>
          </div>
        </div>
      </div>

      {/* ... (resto do JSX) */}
    </div>
  );
}