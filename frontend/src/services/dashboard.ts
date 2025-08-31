import type { DashboardSummary } from '@/types';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const res = await fetch(`${API_URL}/dashboard/summary`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Falha ao carregar dashboard');
  return res.json();
};

