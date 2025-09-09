'use client';

import { useState, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function EditalUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [orgao, setOrgao] = useState('');
  const [objeto, setObjeto] = useState('');
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setFile(event.target.files[0]);
      setMessage('');
    }
  };

  const handleUpload = useCallback(async () => {
    if (!file) {
      setMessage('Por favor, selecione um arquivo.');
      return;
    }

    setUploading(true);
    setMessage('Enviando arquivo...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('orgao_entidade_nome', orgao);
    formData.append('objeto_compra', objeto);

    try {
      const response = await fetch(`${API_URL}/upload/edital/`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Ocorreu um erro no upload.');
      }

      setMessage(`Sucesso! Análise iniciada para o arquivo ${result.filename}. ID da Análise: ${result.analise_id}`);
      setFile(null);
      setOrgao('');
      setObjeto('');
    } catch (error: any) {
      setMessage(`Erro: ${error.message}`);
    } finally {
      setUploading(false);
    }
  }, [file, orgao, objeto]);

  return (
    <div className="p-4 bg-white rounded-lg border border-gray-200 shadow-sm mb-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-2">Análise de Edital Manual</h3>
      <p className="text-sm text-gray-600 mb-4">
        Se a busca automática não encontrou um edital ou falhou na extração, envie o arquivo PDF manualmente para que a IA possa analisá-lo.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
        <div className="md:col-span-2">
            <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-1">Arquivo do Edital (PDF)</label>
            <input 
                id="file-upload"
                type="file" 
                accept=".pdf"
                onChange={handleFileChange} 
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" 
            />
        </div>
        <div className="flex flex-col gap-2">
            <input 
                type="text"
                value={orgao}
                onChange={(e) => setOrgao(e.target.value)}
                placeholder="Órgão (opcional)"
                className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
            />
            <input 
                type="text"
                value={objeto}
                onChange={(e) => setObjeto(e.target.value)}
                placeholder="Objeto da licitação (opcional)"
                className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
            />
        </div>
      </div>
      <div className="mt-4 flex items-center gap-4">
        <button 
            onClick={handleUpload} 
            disabled={!file || uploading}
            className="px-6 py-2 bg-purple-600 text-white font-semibold rounded-md hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
            {uploading ? 'Enviando...' : 'Enviar para Análise'}
        </button>
        {message && <p className="text-sm text-gray-700">{message}</p>}
      </div>
    </div>
  );
}
