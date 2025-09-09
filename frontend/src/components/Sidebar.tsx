'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import LogoBranca from './LogoBranca';
import { HomeIcon, LightbulbIcon, PieChartIcon, DollarSignIcon, BriefcaseIcon, MagnifyingGlassIcon } from './SidebarIcons';

// Componente para um item de navegação, para manter o código limpo
type NavItemProps = {
  href: string;
  icon: React.ReactNode;
  isActive: boolean;
  children: React.ReactNode;
};

const NavItem = ({ href, icon, isActive, children }: NavItemProps) => {
  const activeClass = isActive ? 'bg-blue-800 outline outline-2 outline-licitai-blue-accent' : '';

  return (
    <li>
      <Link href={href} className={`flex items-center p-3 text-gray-200 hover:bg-blue-800 rounded-md transition-colors duration-200 ${activeClass}`}>
        <span className="mr-3">{icon}</span>
        {children}
      </Link>
    </li>
  );
};


export default function Sidebar() {
  const pathname = usePathname();

  // Lista de itens de navegação para facilitar a manutenção
  const navItems = [
    { label: 'Dashboard', href: '/dashboard', icon: <PieChartIcon className="w-5 h-5" /> },
    { label: 'Oportunidades', href: '/dashboard/oportunidades', icon: <LightbulbIcon className="w-5 h-5" /> },
    { label: 'Análises', href: '/dashboard/analises', icon: <MagnifyingGlassIcon className="w-5 h-5" /> },
    { label: 'Preços', href: '/dashboard/precos', icon: <DollarSignIcon className="w-5 h-5" /> },
    { label: 'Auxiliar Jurídico', href: '/juridico', icon: <BriefcaseIcon className="w-5 h-5" /> },
  ];

  return (
    <aside className="w-56 h-screen bg-blue-700 text-white flex flex-col shadow-lg">
      <div className="py-4 px-4 border-b border-blue-600">
        {/* A logo será um link para a página inicial */}
        <Link href="/dashboard">
          <div style={{ width: '185.4px', height: '184.2px' }}>
            <div style={{ transform: 'scale(0.6)', transformOrigin: 'top left' }}>
              <LogoBranca />
            </div>
          </div>
        </Link>
      </div>
      
      <nav className="flex-1 px-4 py-6">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <NavItem 
              key={item.label} 
              href={item.href} 
              icon={item.icon}
              isActive={pathname === item.href}
            >
              {item.label}
            </NavItem>
          ))}
        </ul>
      </nav>

      <div className="p-4 border-t border-blue-600">
        {/* Espaço reservado para informações do usuário ou botão de sair no futuro */}
      </div>
    </aside>
  );
}
