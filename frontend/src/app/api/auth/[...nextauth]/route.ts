import NextAuth, { AuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

// O tipo de usuário que nossa API retorna após o login bem-sucedido
interface ApiUser {
  id: number;
  email: string;
  nickname: string | null;
}

export const authOptions: AuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: "Email", type: "text" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials): Promise<ApiUser | null> {
        if (!credentials) {
          return null;
        }

        // O backend com OAuth2PasswordRequestForm espera dados de formulário, não JSON.
        const email = (credentials.email ?? '').trim();
        const password = credentials.password ?? '';
        if (!email || !password) { return null; }

        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        try {
          const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
          const controller = new AbortController();
          const timeoutMs = Number(process.env.NEXTAUTH_LOGIN_TIMEOUT_MS || 10000);
          const t = setTimeout(() => controller.abort(), timeoutMs);
          const res = await fetch(`${baseUrl}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString(),
            signal: controller.signal,
            cache: 'no-store',
          });
          clearTimeout(t);

          if (!res.ok) {
            console.error("Falha no login, status:", res.status);
            return null;
          }

          const user: ApiUser = await res.json();

          // Se a resposta for bem-sucedida e tivermos um usuário, retorne-o.
          if (user) {
            return user;
          } else {
            return null;
          }
        } catch (error) {
          console.error("Erro de rede ou conexão ao tentar fazer login:", error);
          return null;
        }
      }
    })
  ],
  callbacks: {
    // O callback 'jwt' Ã© chamado ao criar ou atualizar um JSON Web Token.
    async jwt({ token, user }) {
      // O objeto 'user' só estÃ¡ presente no primeiro login.
      // Persistimos os dados do usuário (id e nickname) no token.
      if (user) {
        const apiUser = user as ApiUser;
        token.id = apiUser.id;
        token.nickname = apiUser.nickname;
      }
      return token;
    },
    // O callback 'session' Ã© chamado quando um cliente verifica a sessão.
    async session({ session, token }) {
      // Adicionamos os dados do token (id e nickname) para o objeto da sessão do cliente.
      if (session.user) {
        // O TypeScript precisa que a gente estenda o tipo 'Session' para reconhecer as novas propriedades.
        // Faremos isso no próximo passo.
        (session.user as any).id = token.id;
        (session.user as any).nickname = token.nickname;
      }
      return session;
    }
  },
  session: {
    strategy: "jwt",
  },
  // Redireciona páginas do NextAuth para a tela de login
  pages: {
    signIn: "/login",
    error: "/login",
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };




