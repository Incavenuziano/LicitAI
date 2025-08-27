import NextAuth, { AuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

// O tipo de usuário que nossa API retorna após o login bem-sucedido
interface ApiUser {
  id: number;
  email: string;
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
        const formData = new URLSearchParams();
        formData.append('username', credentials.email); // O formulário do FastAPI usa 'username' para o email.
        formData.append('password', credentials.password);

        try {
          const res = await fetch('http://localhost:8000/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString(),
          });

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
    // O callback 'jwt' é chamado ao criar ou atualizar um JSON Web Token.
    async jwt({ token, user }) {
      // O objeto 'user' só está presente no primeiro login.
      // Adicionamos o ID do usuário ao token para que ele persista.
      if (user) {
        token.id = (user as ApiUser).id;
      }
      return token;
    },
    // O callback 'session' é chamado quando um cliente verifica a sessão.
    async session({ session, token }) {
      // Adicionamos o ID do usuário do token para o objeto da sessão do cliente.
      if (session.user) {
        // O TypeScript precisa que a gente estenda o tipo 'Session' para reconhecer 'id'.
        // Faremos isso no próximo passo. Por enquanto, usamos 'as any'.
        (session.user as any).id = token.id; 
      }
      return session;
    }
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
