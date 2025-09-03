'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/dashboard');
  }, [router]);

  // Renderiza um componente de loading para evitar uma tela em branco durante o redirecionamento
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <p>Carregando...</p>
    </div>
  );
}
