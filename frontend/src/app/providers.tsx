'use client';

import { SessionProvider } from 'next-auth/react';
import React from 'react';

interface Props {
  children: React.ReactNode;
}

/**
 * Um componente de wrapper que fornece o contexto da sessão do NextAuth
 * para os componentes filhos. Marcado como 'use client' porque o SessionProvider
 * usa o React Context, que é um recurso de cliente.
 */
export default function Providers({ children }: Props) {
  return <SessionProvider>{children}</SessionProvider>;
}
