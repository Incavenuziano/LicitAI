'use client';

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getLicitacoes,
  LicitacaoFilters,
  requestAnalises,
  buscarLicitacoes,
  ragIndexar,
  ragPerguntar,
} from "@/services/api";
import { Licitacao, Analise } from "@/types";
import EditalUploader from "./EditalUploader";

const UFS_BR = [
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
] as const;

const StatusAnalise: React.FC<{
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
  const isConcluido =
    analise.status === "Concluído" || analise.status === "Concluido";
  return (
    <div className="flex flex-col items-center gap-1">
      <span
        className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusStyle(
          analise.status
        )}`}
      >
        {analise.status}
      </span>
      {isConcluido && (
        <button onClick={onVerResultado} className="text-xs text-blue-600 hover:underline">
          Ver Resultado
        </button>
      )}
    </div>
  );
};

const getClassificacao = (objeto: string | null): string => {
  if (!objeto) return "Outros";
  const strip = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
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

export default function OportunidadesTabela() {
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
    setLicitacoes(Array.isArray(data) ? data : []);
    setLoading(false);
  };

  useEffect(() => {
    const debounceHandler = setTimeout(() => {
      fetchData({ q: filtroQ, uf: filtroUF });
    }, 500);

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
    let licitacoesProcessadas = Array.isArray(licitacoes) ? [...licitacoes] : [];
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
      const answer = r.results && r.results.length > 0
        ? r.results.map((x: any) => x.chunk).join("\n\n---\n\n")
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
      <EditalUploader />
      <div className="p-4 bg-gray-50 rounded-lg border mb-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
              Encerramento Entre
            </label>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
              />
              <input
                type="date"
                value={dataFim}
                onChange={(e) => setDataFim(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
              />
            </div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => setOrdemValor("asc")}
            className={`p-2 text-sm rounded-md ${
              ordemValor === "asc" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
          >
            Valor Crescente
          </button>
          <button
            onClick={() => setOrdemValor("desc")}
            className={`p-2 text-sm rounded-md ${
              ordemValor === "desc" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
          >
            Valor Decrescente
          </button>
          <button
            onClick={() => {
              setFiltroQ("");
              setFiltroUF("");
              setDataInicio("");
              setDataFim("");
              setFiltroTipo("");
            }}
            className="p-2 text-sm bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
          >
            Limpar Filtros
          </button>
          <button
            onClick={handleBuscarNovas}
            className="p-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:bg-gray-400"
            disabled={isFetchingNew}
          >
            {isFetchingNew ? "Buscando..." : "Buscar Novas"}
          </button>
        </div>
      </div>

      {selectedAnalise && (
        <div className="mb-3 p-4 bg-blue-50 border border-blue-200 rounded">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-bold">
              Resultado da Análise
              {selectedAnalise.orgao ? ` - ${selectedAnalise.orgao}` : ""}
              {selectedAnalise.numero ? ` - ${selectedAnalise.numero}` : ""}
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (selectedAnalise?.resultado)
                    navigator.clipboard.writeText(selectedAnalise.resultado);
                }}
                className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Copiar resultado
              </button>
              <button
                onClick={() => setSelectedAnalise(null)}
                className="px-3 py-1 text-sm bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
              >
                Limpar resultado
              </button>
            </div>
          </div>
          <div className="whitespace-pre-wrap bg-white p-3 rounded border border-blue-100 font-mono text-sm max-h-96 overflow-auto">
            {selectedAnalise.resultado}
            <div className="mt-3 rounded border border-blue-100 bg-white p-3">
              <h4 className="font-semibold mb-2 text-sm">Perguntar ao Edital (RAG)</h4>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={ragQuestion}
                  onChange={(e) => setRagQuestion(e.target.value)}
                  placeholder="Ex.: Data limite para entrega? Garantia exigida?"
                  className="flex-1 px-3 py-2 border rounded"
                />
                <button
                  onClick={async () => {
                    if (!selectedAnalise?.id) return;
                    setRagIndexing(true);
                    try {
                      await ragIndexar(selectedAnalise.id);
                    } catch (e: any) {
                      alert(e?.message || "Falha ao indexar");
                    } finally {
                      setRagIndexing(false);
                    }
                  }}
                  className="px-3 py-2 bg-gray-200 rounded hover:bg-gray-300"
                  disabled={ragIndexing}
                >
                  {ragIndexing ? "Indexando..." : "Indexar"}
                </button>
                <button
                  onClick={handleRagAsk}
                  disabled={ragLoading || !ragQuestion.trim()}
                  className="px-3 py-2 bg-indigo-600 text-white rounded disabled:bg-gray-400"
                >
                  {ragLoading ? "Perguntando..." : "Perguntar"}
                </button>
              </div>
              {ragAnswers.length > 0 && (
                <div className="space-y-3 max-h-64 overflow-auto">
                  {ragAnswers.map((m, idx) => (
                    <div key={idx} className="text-sm">
                      <div className="text-gray-600">Q: {m.q}</div>
                      <div className="whitespace-pre-wrap mt-1 border rounded p-2 bg-gray-50">
                        {m.a}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-2 h-9">
        <div className="text-sm text-gray-600">
          {selectedIds.size > 0 && (
            <span>
              {selectedIds.size} de {licitacoesExibidas.length} itens selecionados.
            </span>
          )}
        </div>
        {selectedIds.size > 0 && (
          <div className="flex gap-2">
            <button
              onClick={handleAnalisar}
              className="px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-md hover:bg-purple-700 disabled:bg-gray-400"
              disabled={selectedIds.size === 0 || isAnalysing}
            >
              {isAnalysing ? "Analisando..." : "Analisar Selecionados"}
            </button>
            <button
              onClick={handleExport}
              className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:bg-gray-400"
              disabled={selectedIds.size === 0}
            >
              Exportar Selecionados (CSV)
            </button>
          </div>
        )}
      </div>

      <div className="rounded-lg border bg-white shadow-sm">
        <div className="max-h-[70vh] overflow-y-auto overflow-x-auto">
          {!loading && licitacoesExibidas.length > 0 && (
            <table className="min-w-[1000px] w-full text-sm table-fixed">
              <thead className="sticky top-0 z-10 bg-gray-50">
                <tr>
                  <th className="py-3 px-3 border-b border-gray-200 w-12 text-center whitespace-nowrap">
                    <input
                      type="checkbox"
                      ref={selectAllCheckboxRef}
                      checked={
                        licitacoesExibidas.length > 0 &&
                        selectedIds.size === licitacoesExibidas.length
                      }
                      onChange={handleSelectAll}
                      className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </th>
                  <th className="py-2 px-4 border-b w-1/6">Órgão</th>
                  <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700 w-1/3">
                    Objeto
                  </th>
                  <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700 whitespace-normal">
                    Data de Encerramento
                  </th>
                  <th className="py-3 px-4 border-b border-gray-200 text-right font-semibold text-gray-700 whitespace-normal w-1/6">
                    Valor Estimado
                  </th>
                  <th className="py-3 px-4 border-b border-gray-200 text-center font-semibold text-gray-700">
                    Edital
                  </th>
                  <th className="py-3 px-4 border-b border-gray-200 text-center font-semibold text-gray-700">
                    Preços
                  </th>
                  <th className="py-2 px-4 border-b">{"Status da Análise"}</th>
                </tr>
              </thead>
              <tbody>
                {licitacoesExibidas.map((licitacao) => (
                  <tr
                    key={licitacao.id}
                    onClick={() => router.push(`/dashboard/licitacoes/${licitacao.id}`)}
                    className={`${
                      selectedIds.has(licitacao.id)
                        ? "bg-blue-100"
                        : "odd:bg-gray-50 hover:bg-gray-100"
                    } cursor-pointer`}
                  >
                    <td className="py-2 px-3 border-b text-center whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(licitacao.id)}
                        onClick={(e) => e.stopPropagation()}
                        onChange={() => handleSelect(licitacao.id)}
                        className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="py-2 px-4 border-b whitespace-normal">
                      {licitacao.orgao_entidade_nome}
                    </td>
                    <td className="py-2 px-4 border-b whitespace-normal break-words">
                      {licitacao.objeto_compra}
                    </td>
                    <td className="py-2 px-4 border-b whitespace-nowrap">
                      {licitacao.data_encerramento_proposta
                        ? new Date(
                            licitacao.data_encerramento_proposta
                          ).toLocaleDateString("pt-BR")
                        : "N/A"}
                    </td>
                    <td className="py-2 px-4 border-b text-right whitespace-nowrap">
                      {licitacao.valor_total_estimado
                        ? parseFloat(licitacao.valor_total_estimado).toLocaleString(
                            "pt-BR",
                            {
                              style: "currency",
                              currency: "BRL",
                            }
                          )
                        : "N/A"}
                    </td>
                    <td
                      className="py-2 px-4 border-b text-center whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {licitacao.link_sistema_origem ? (
                        <a
                          href={licitacao.link_sistema_origem}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded text-sm"
                        >
                          Acessar
                        </a>
                      ) : (
                        "N/D"
                      )}
                    </td>
                    <td
                      className="py-2 px-4 border-b text-center whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Link
                        href={`/precos/${licitacao.id}`}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-1 px-2 rounded text-sm"
                      >
                        Preços
                      </Link>
                    </td>
                    <td
                      className={`py-2 px-4 border-b text-center ${(() => {
                        const st =
                          licitacao.analises && licitacao.analises[0]
                            ? licitacao.analises[0].status
                            : undefined;
                        const s = String(st).toLowerCase();
                        if (s === "processando") return "bg-yellow-50";
                        if (s === "erro") return "bg-red-50";
                        if (s.startsWith("conclu")) return "bg-green-50";
                        return "";
                      })()}`}
                    >
                      <StatusAnalise
                        analise={licitacao.analises && licitacao.analises[0]}
                        onVerResultado={() => handleShowResultado(licitacao)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
