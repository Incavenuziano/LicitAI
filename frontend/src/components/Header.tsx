'use client';

import { useSession, signOut } from 'next-auth/react';

// Componentes de Ícones (substituíveis por uma biblioteca de ícones se preferir)
const SearchIcon = () => (
  <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
);

const UserIcon = () => (
    <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
);

const LogoutIcon = () => (
    <svg className="w-6 h-6 text-red-500 hover:text-red-700 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
);

export default function Header() {
  const { data: session } = useSession();

  return (
    <header className="bg-white shadow-sm p-4 flex items-center justify-between z-10">
      {/* Search Bar */}
      <div className="relative w-full max-w-xl">
        <span className="absolute left-4 top-1/2 -translate-y-1/2">
          <SearchIcon />
        </span>
        <input
          type="text"
          placeholder="Buscar em toda a plataforma..."
          className="w-full bg-gray-100 border-transparent rounded-full py-2 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow"
        />
      </div>

      {/* User Area */}
      <div className="flex items-center space-x-4 ml-4">
        <UserIcon />
        <span className="text-gray-700 hidden sm:inline">Olá, {session?.user?.nickname || session?.user?.email}</span>
        <button onClick={() => signOut({ callbackUrl: '/login' })} title="Sair" className="p-1 rounded-full hover:bg-gray-100 transition-colors">
          <LogoutIcon />
        </button>
      </div>
    </header>
  );
}
