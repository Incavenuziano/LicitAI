'use client';

import { useState, useEffect } from 'react';
import { getOportunidadesAtivas, OportunidadesPayload, salvarLicitacoesDireto, getPncpModalidades, ModalidadeInfo } from '@/services/api';

const UFS_BR = [
  'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
];

// Modalidades serÃ£o carregadas dinamicamente do backend

type Row = any;

export default function OportunidadesAbertas() {
  const [uf, setUf] = useState('');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');
  const [modalidadeSel, setModalidadeSel] = useState<string>(''); // '', 'custom', or numeric as string
  const [modalidadeCustom, setModalidadeCustom] = useState<string>('');
  const [modalidades, setModalidades] = useState<ModalidadeInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [amplo, setAmplo] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [busca, setBusca] = useState('');

  const fetchSimple = async () => {
    setLoading(true);
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
    } catch (e: any) {
      alert(e?.message || 'Falha ao consultar oportunidades');
    } finally {
      setLoading(false);
    }
  };

  const fetchAmplo = async () => {
    setLoading(true);
    try {
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
      const data = await getOportunidadesAtivas(payload);
      setRows(data);
    } catch (e: any) {
      alert(e?.message || 'Falha ao consultar oportunidades (amplo)');
    } finally {
      setLoading(false);
    }
  };

  const handleBuscar = () => (amplo ? fetchAmplo() : fetchSimple());

  // Carrega modalidades dinamicamente na montagem
  useEffect(() => {
    (async () => {
      try {
        const mods = await getPncpModalidades();
        setModalidades(mods);
      } catch {}
    })();
  }, []);

  const terms = busca
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => !!t);

  const view: { r: Row; i: number }[] = rows
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
        const hay = parts.join(' ').toLowerCase();
        return terms.every((t) => hay.includes(t));
      } catch {
        return false;
      }
    });

  const toggleAll = () => {
    const allSelected = view.length > 0 && view.every(({ i }) => selected.has(i));
    if (allSelected) {
      // desmarca apenas os visÃ­veis
      const n = new Set(selected);
      view.forEach(({ i }) => n.delete(i));
      setSelected(n);
    } else {
      const n = new Set(selected);
      view.forEach(({ i }) => n.add(i));
      setSelected(n);
    }
  };

  const toggleIdx = (idx: number) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(idx)) n.delete(idx); else n.add(idx);
      return n;
    });
  };

  const handleSalvarSelecionadas = async () => {
    if (selected.size === 0) return;
    setSaving(true);
    try {
      const items = Array.from(selected).map((i) => rows[i]);
      const r = await salvarLicitacoesDireto(items);
      alert(typeof r === 'object' ? JSON.stringify(r) : String(r));
    } catch (e: any) {
      alert(e?.message || 'Falha ao salvar licitaÃ§Ãµes');
    } finally {
      setSaving(false);
    }
  };

  const cols = [
    { key: 'numeroControlePNCP', label: 'Controle PNCP' },
    { key: 'orgaoEntidade.razaoSocial', label: 'Ã“rgÃ£o' },
    { key: 'unidadeOrgao.ufSigla', label: 'UF' },
    { key: 'objetoCompra', label: 'Objeto' },
    { key: 'dataEncerramentoProposta', label: 'Encerramento Proposta' },
    { key: 'linkSistemaOrigem', label: 'Link' },
  ];

  const get = (obj: any, path: string) => {
    try {
      return path.split('.').reduce((o, k) => (o ? o[k] : undefined), obj);
    } catch {
      return undefined;
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 p-4 bg-gray-50 rounded border">
        <div>
          <label className="block text-sm mb-1">UF</label>
          <select value={uf} onChange={(e) => setUf(e.target.value)} className="w-full p-2 border rounded">
            <option value="">Todas</option>
            {UFS_BR.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1">Data inÃ­cio</label>
          <input type="date" value={dataInicio} onChange={(e) => setDataInicio(e.target.value)} className="w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm mb-1">Data fim</label>
          <input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} className="w-full p-2 border rounded" />
        </div>
        <div>
          <label className="block text-sm mb-1">Modalidade</label>
          <select
            value={modalidadeSel}
            onChange={(e) => setModalidadeSel(e.target.value)}
            className="w-full p-2 border rounded mb-2"
          >
            <option value="">(Sem filtro)</option>
            {modalidades.map((m) => (
              <option key={m.code} value={String(m.code)}>{m.label} ({m.code})</option>
            ))}
            <option value="custom">Outro (digitar cÃ³digo)</option>
          </select>
          {modalidadeSel === 'custom' && (
            <input
              type="number"
              placeholder="CÃ³digo da modalidade (numÃ©rico)"
              value={modalidadeCustom}
              onChange={(e) => setModalidadeCustom(e.target.value)}
              className="w-full p-2 border rounded"
            />
          )}
        </div>
        <div className="flex items-end gap-3">
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={amplo} onChange={(e) => setAmplo(e.target.checked)} /> Varredura ampla
          </label>
          <button onClick={handleBuscar} disabled={loading} className="px-4 py-2 bg-indigo-600 text-white rounded disabled:bg-gray-400">
            {loading ? 'Buscando...' : 'Buscar'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-gray-600">
        <div className="flex items-center gap-2">
          <span>{view.length} oportunidade(s)</span>
          {rows.length !== view.length && (
            <span className="text-gray-400">(de {rows.length})</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>{selected.size} selecionada(s)</span>
          <button
            onClick={handleSalvarSelecionadas}
            disabled={selected.size === 0 || saving}
            className="px-3 py-1 bg-green-600 text-white rounded disabled:bg-gray-400"
          >
            {saving ? 'Salvando...' : 'Salvar Selecionadas'}
          </button>
        </div>
      </div>

      {/* Busca local na lista baixada */}
      <div className="flex items-center gap-2 text-sm">
        <input
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Filtrar por palavra (objeto, Ã³rgÃ£o, UF, PNCP)"
          className="w-full md:w-96 p-2 border rounded"
        />
        {busca && (
          <button className="px-3 py-2 bg-gray-200 rounded" onClick={() => setBusca('')}>Limpar</button>
        )}
      </div>

      <div className="rounded border bg-white overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              <th className="p-2 border-b">
                <input type="checkbox" onChange={toggleAll} checked={view.length>0 && view.every(({i})=> selected.has(i))} />
              </th>
              {cols.map((c) => (
                <th key={c.key} className="text-left p-2 border-b">{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.map(({ r, i }) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="p-2 border-b">
                  <input type="checkbox" checked={selected.has(i)} onChange={() => toggleIdx(i)} />
                </td>
                {cols.map((c) => (
                  <td key={c.key} className="p-2 border-b">
                    {c.key === 'linkSistemaOrigem' ? (
                      (() => {
                        const href = get(r, c.key);
                        return href ? (
                          <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">abrir</a>
                        ) : null;
                      })()
                    ) : (
                      String(get(r, c.key) ?? '')
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}



