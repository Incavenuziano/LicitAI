import NextAuth, { AuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

// O tipo de usuÃ¡rio que nossa API retorna apÃ³s o login bem-sucedido
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

        // O backend com OAuth2PasswordRequestForm espera dados de formulÃ¡rio, nÃ£o JSON.
        const formData = new URLSearchParams();
        formData.append('username', credentials.email); // O formulÃ¡rio do FastAPI usa 'username' para o email.
        formData.append('password', credentials.password);

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

          // Se a resposta for bem-sucedida e tivermos um usuÃ¡rio, retorne-o.
          if (user) {
            return user;
          } else {
            return null;
          }
        } catch (error) {
          console.error("Erro de rede ou conexÃ£o ao tentar fazer login:", error);
          return null;
        }
      }
    })
  ],
  callbacks: {
    // O callback 'jwt' Ã© chamado ao criar ou atualizar um JSON Web Token.
    async jwt({ token, user }) {
      // O objeto 'user' sÃ³ estÃ¡ presente no primeiro login.
      // Persistimos os dados do usuÃ¡rio (id e nickname) no token.
      if (user) {
        const apiUser = user as ApiUser;
        token.id = apiUser.id;
        token.nickname = apiUser.nickname;
      }
      return token;
    },
    // O callback 'session' Ã© chamado quando um cliente verifica a sessÃ£o.
    async session({ session, token }) {
      // Adicionamos os dados do token (id e nickname) para o objeto da sessÃ£o do cliente.
      if (session.user) {
        // O TypeScript precisa que a gente estenda o tipo 'Session' para reconhecer as novas propriedades.
        // Faremos isso no prÃ³ximo passo.
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

