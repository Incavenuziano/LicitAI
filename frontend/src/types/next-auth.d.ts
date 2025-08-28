import 'next-auth';
import 'next-auth/jwt';

/**
 * Estende os tipos padrão do NextAuth para incluir as propriedades customizadas
 * que adicionamos no token e na sessão.
 */

declare module 'next-auth' {
  /**
   * O objeto `Session` retornado pela função `useSession` ou `getSession`.
   */
  interface Session {
    user?: {
      id?: number | null;
      nickname?: string | null;
    } & DefaultSession['user']; // Mantém os campos padrão (name, email, image)
  }

  /**
   * O objeto `User` retornado pela função `authorize` do provider.
   */
  interface User {
    id?: number | null;
    nickname?: string | null;
  }
}

declare module 'next-auth/jwt' {
  /**
   * O token JWT decodificado.
   */
  interface JWT {
    id?: number | null;
    nickname?: string | null;
  }
}