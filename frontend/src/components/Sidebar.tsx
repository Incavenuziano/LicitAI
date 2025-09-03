import Link from 'next/link';
import LogoBranca from './LogoBranca';

// Componente para um item de navegação, para manter o código limpo
type NavItemProps = {
  href: string;
  children: React.ReactNode;
};

const NavItem = ({ href, children }: NavItemProps) => {
  return (
    <li>
      <Link href={href} className="flex items-center p-3 text-gray-200 hover:bg-blue-800 rounded-md transition-colors duration-200">
        {children}
      </Link>
    </li>
  );
};


export default function Sidebar() {
  // Lista de itens de navegação para facilitar a manutenção
  const navItems = [
    { label: 'Dashboard', href: '/' },
    { label: 'Oportunidades', href: '/oportunidades' },
    { label: 'Análises', href: '/analises' },
    { label: 'Preços', href: '/precos' },
    { label: 'Auxiliar Jurídico', href: '/juridico' },
  ];

  return (
    <aside className="w-72 h-screen bg-blue-700 text-white flex flex-col shadow-lg">
      <div className="flex items-center p-6 border-b border-blue-600">
        {/* A logo será um link para a página inicial */}
        <Link href="/">
            <LogoBranca className="w-24 h-auto" />
        </Link>
      </div>
      
      <nav className="flex-1 px-4 py-6">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <NavItem key={item.label} href={item.href}>
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
