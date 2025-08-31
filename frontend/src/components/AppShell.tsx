"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import React from "react";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const authed = status === "authenticated";

  if (!authed) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar à esquerda (apenas autenticado) */}
      <aside className="hidden md:block w-64 shrink-0 border-r bg-white">
        <div className="h-full flex flex-col p-4 gap-4">
          <div className="text-lg font-semibold text-gray-800">LicitAI</div>
          <nav className="flex-1 text-sm text-gray-700">
            <ul className="space-y-1">
              <li>
                <Link href="/" className="block rounded px-3 py-2 hover:bg-gray-100">Início</Link>
              </li>
              <li>
                <Link href="/licitacoes" className="block rounded px-3 py-2 hover:bg-gray-100">Licitações</Link>
              </li>
              <li>
                <Link href="/precos" className="block rounded px-3 py-2 hover:bg-gray-100">Preços</Link>
              </li>
            </ul>
          </nav>
          <div className="text-xs text-gray-400">v0.1</div>
        </div>
      </aside>
      {/* Área principal */}
      <div className="flex-1 min-w-0">
        <div className="mx-auto max-w-5xl px-6 py-8">
          {children}
        </div>
      </div>
    </div>
  );
}
