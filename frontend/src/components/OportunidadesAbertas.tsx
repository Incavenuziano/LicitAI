'use client';

import { useEffect, useState, useRef } from 'react';
import {
  getOportunidadesAtivas,
  OportunidadesPayload,
  salvarLicitacoesDireto,
  getPncpModalidades,
  ModalidadeInfo,
} from '@/services/api';

const UFS_BR = [
  'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
];

type Row = any;

type ViewItem = {
  r: Row;
  i: number;
};

const COLS: { key: string; label: string }[] = [
  { key: 'numeroControlePNCP', label: 'Controle PNCP' },
  { key: 'orgaoEntidade.razaoSocial', label: 'Orgao' },
  { key: 'unidadeOrgao.ufSigla', label: 'UF' },
  { key: 'objetoCompra', label: 'Objeto' },
  { key: 'dataEncerramentoProposta', label: 'Encerramento Proposta' },
  { key: 'linkSistemaOrigem', label: 'Link' },
];

const getValue = (obj: any, path: string) => {
  try {
    return path.split('.').reduce((curr: any, key) => {
      if (curr === null || curr === undefined) return undefined;
      return curr[key];
    }, obj);
  } catch {
    return undefined;
  }
};

export default function OportunidadesAbertas() {
  const [uf, setUf] = useState('');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');
  const [modalidadeSel, setModalidadeSel] = useState<string>('');
  const [modalidadeCustom, setModalidadeCustom] = useState<string>('');
  const [modalidades, setModalidades] = useState<ModalidadeInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [amplo, setAmplo] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [busca, setBusca] = useState('');
  const [searchLog, setSearchLog] = useState<string[]>([]);
  const ws = useRef<WebSocket | null>(null);

  const fetchSimple = async () => {
    setLoading(true);
    setSearchLog([]);
    try {
      const codigoModalidade = modalidadeSel === 'custom'
        ? (modalidadeCustom ? Number(modalidadeCustom) : undefined)
        : (modalidadeSel ? Number(modalidadeSel) : undefined);

      const payload: OportunidadesPayload = {
        uf: uf || undefined,
        data_inicio: dataInicio || undefined,
        data_fim: dataFim || undefined,
        codigo_modalidade: codigoModalidade,
        pagina: 1,
        tamanho_pagina: 50,
      };
      const data = await getOportunidadesAtivas(payload);
      setRows(data);
    } catch (error: any) {
      alert(error?.message || 'Falha ao consultar oportunidades');
    } finally {
      setLoading(false);
    }
  };

  const fetchAmplo = () => {
    setLoading(true);
    setRows([]);
    setSearchLog(['Iniciando conexão com o servidor...']);

    // Garantir que a URL do WebSocket está correta para o ambiente
    const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000/ws/busca-ampla';
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setSearchLog(prev => [...prev, 'Conexão estabelecida. Enviando parâmetros de busca...']);
      const codigoModalidade = modalidadeSel === 'custom'
        ? (modalidadeCustom ? Number(modalidadeCustom) : undefined)
        : (modalidadeSel ? Number(modalidadeSel) : undefined);

      const payload: OportunidadesPayload = {
        amplo: true,
        total_days: 14,
        step_days: 7,
        ufs: uf ? [uf] : undefined,
        modal_codes: typeof codigoModalidade === 'number' ? [codigoModalidade] : undefined,
        page_limit: 25,
        tamanho_pagina: 50,
        data_fim_ref: dataFim || undefined,
      };
      ws.current?.send(JSON.stringify(payload));
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'progress' || message.type === 'start' || message.type === 'done') {
        setSearchLog(prev => [...prev, message.message]);
      }

      if (message.type === 'result') {
        setSearchLog(prev => [...prev, `Busca finalizada. Total de ${message.meta.total_items} itens encontrados.`]);
        setRows(message.data);
      }

      if (message.type === 'error') {
        setSearchLog(prev => [...prev, `ERRO: ${message.message}`]);
        alert(`Erro no servidor: ${message.message}`);
      }
    };

    ws.current.onerror = (event) => {
      console.error("WebSocket error observed:", event);
      setSearchLog(prev => [...prev, 'Erro na conexão WebSocket. Verifique o console.']);
      alert('Não foi possível conectar ao servidor para a busca em tempo real.');
      setLoading(false);
    };

    ws.current.onclose = () => {
      setSearchLog(prev => [...prev, 'Conexão com o servidor encerrada.']);
      setLoading(false);
    };
  };

  const handleBuscar = () => (amplo ? fetchAmplo() : fetchSimple());

  useEffect(() => {
    (async () => {
      try {
        const mods = await getPncpModalidades();
        setModalidades(mods);
      } catch {
        // silencia falha no carregamento inicial
      }
    })();

    // Limpeza ao desmontar o componente
    return () => {
      ws.current?.close();
    };
  }, []);

  const terms = busca
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => !!t);

  const view: ViewItem[] = rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => {
      if (terms.length === 0) return true;
      try {
        const parts: string[] = [];
        parts.push(String(r?.numeroControlePNCP ?? ''));
        parts.push(String(r?.objetoCompra ?? ''));
        parts.push(String(r?.orgaoEntidade?.razaoSocial ?? ''));
        parts.push(String(r?.unidadeOrgao?.ufSigla ?? ''));
        parts.push(String(r?.unidadeOrgao?.municipioNome ?? ''));
        const haystack = parts.join(' ').toLowerCase();
        return terms.every((t) => haystack.includes(t));
      } catch {
        return false;
      }
    });

  const toggleAll = () => {
    const allSelected = view.length > 0 && view.every(({ i }) => selected.has(i));
    if (allSelected) {
      const next = new Set(selected);
      view.forEach(({ i }) => next.delete(i));
      setSelected(next);
    } else {
      const next = new Set(selected);
      view.forEach(({ i }) => next.add(i));
      setSelected(next);
    }
  };

  const toggleIdx = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const handleSalvarSelecionadas = async () => {
    if (selected.size === 0) return;
    setSaving(true);
    try {
      const items = Array.from(selected).map((i) => rows[i]);
      const response = await salvarLicitacoesDireto(items);
      alert(typeof response === 'object' ? JSON.stringify(response) : String(response));
    } catch (error: any) {
      alert(error?.message || 'Falha ao salvar licitacoes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 p-4 bg-gray-50 rounded border">
        {/* Filtros ... */}
        <div>
          <label className="block text-sm mb-1">UF</label>
          <select value={uf} onChange={(event) => setUf(event.target.value)} className="w-full p-2 border rounded">
            <option value="">Todas</option>
            {UFS_BR.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1">Data inicio</label>
          <input type="date" value={dataInicio} onChange={(event) => setDataInicio(event.target.value)} className="w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm mb-1">Data fim</label>
          <input type="date" value={dataFim} onChange={(event) => setDataFim(event.target.value)} className="w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm mb-1">Modalidade</label>
          <select
            value={modalidadeSel}
            onChange={(event) => setModalidadeSel(event.target.value)}
            className="w-full p-2 border rounded mb-2"
          >
            <option value="">(Sem filtro)</option>
            {modalidades.map((m) => (
              <option key={m.code} value={String(m.code)}>{m.label} ({m.code})</option>
            ))}
            <option value="custom">Outro (digitar codigo)</option>
          </select>
          {modalidadeSel === 'custom' && (
            <input
              type="number"
              placeholder="Codigo da modalidade (numerico)"
              value={modalidadeCustom}
              onChange={(event) => setModalidadeCustom(event.target.value)}
              className="w-full p-2 border rounded"
            />
          )}
        </div>
        <div className="flex items-end gap-3">
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={amplo} onChange={(event) => setAmplo(event.target.checked)} /> Varredura ampla
          </label>
          <button onClick={handleBuscar} disabled={loading} className="px-4 py-2 bg-indigo-600 text-white rounded disabled:bg-gray-400">
            {loading ? 'Buscando...' : 'Buscar'}
          </button>
        </div>
      </div>

      {/* Painel de Log da Busca */}
      {loading && amplo && (
        <div className="p-4 bg-gray-800 text-white rounded-md font-mono text-sm space-y-1 max-h-60 overflow-y-auto">
          <p className="font-bold">Log da Varredura em Tempo Real:</p>
          {searchLog.map((log, index) => (
            <p key={index} className="whitespace-pre-wrap">{`> ${log}`}</p>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-gray-600">
        {/* Contadores e botão de salvar... */}
      </div>

      <div className="flex items-center gap-2 text-sm">
        {/* Filtro de texto ... */}
      </div>

      <div className="rounded border bg-white overflow-auto">
        {/* Tabela ... */}
      </div>
    </div>
  );
}
