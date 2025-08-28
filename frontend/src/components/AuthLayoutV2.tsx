import React from 'react';
import Link from 'next/link';

interface AuthLayoutV2Props {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  visualTitle?: string;
  visualSubtitle?: string;
  showRegisterLink?: boolean;
  showForgotPasswordLink?: boolean;
}

const AuthLayoutV2: React.FC<AuthLayoutV2Props> = ({
  children,
  title = "Login",
  subtitle = "Enter your account details",
  visualTitle = "Bem vindo(a) de volta",
  visualSubtitle = "Acesse sua conta para gerenciar suas licitações de forma inteligente e eficiente.",
  showRegisterLink = true,
  showForgotPasswordLink = true,
}) => {
  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-licitai-bg-light">

      {/* Seção da Esquerda (Formulário) */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 md:p-12">
        <div className="w-full max-w-sm mx-auto"> {/* Added mx-auto here */}
          <h1 className="text-3xl font-bold text-licitai-primary mb-2">{title}</h1>
          <p className="text-sm text-gray-500 mb-8">{subtitle}</p>

          {children} {/* Formulário será renderizado aqui */}

          {showRegisterLink && (
            <div className="mt-8 text-center text-sm">
              <p className="text-gray-500">Don't have an account?</p>
              <Link href="/register" className="font-medium text-licitai-secondary hover:text-licitai-primary mt-2 inline-block">
                Sign up
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Seção da Direita (Elementos Visuais e Logo) */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 md:p-12 bg-licitai-visual-bg relative overflow-hidden">
        {/* Elementos de "blob" de fundo para o efeito da imagem */}
        <div className="absolute inset-0 bg-no-repeat bg-contain bg-center opacity-40">
          {/* SVG do blob - Copiado do HTML fornecido */}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" className="absolute top-0 left-0 w-full h-full">
            <path fill="#C0EEDD" fillOpacity="1" d="M0,192L48,181.3C96,171,192,149,288,138.7C384,128,480,128,576,149.3C672,171,768,213,864,229.3C960,245,1056,235,1152,213.3C1248,192,1344,160,1392,144L1440,128L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"></path>
            <path fill="#A0E0C0" fillOpacity="1" d="M0,32L48,53.3C96,75,192,117,288,144C384,171,480,181,576,176C672,171,768,149,864,133.3C960,117,1056,107,1152,112C1248,117,1344,139,1392,149.3L1440,160L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"></path>
          </svg>
        </div>
        
        {/* Conteúdo do lado direito */}
        <div className="relative z-10 text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-licitai-primary mb-4">
            {visualTitle}
          </h1>
          <p className="text-sm md:text-base text-licitai-secondary mb-8 max-w-sm">
            {visualSubtitle}
          </p>

          {/* Logo */}
          <div className="w-64 h-64 mx-auto mb-8">
            <img
              src="/logo_licitai.png" // Using our actual logo
              alt="LicitAI Logo"
              className="w-full h-full object-contain"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthLayoutV2;
