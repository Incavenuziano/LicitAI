import 'next-auth';
import 'next-auth/jwt';
import type { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    user?: {
      id?: number | null;
      nickname?: string | null;
      backendToken?: string | null;
    } & DefaultSession['user'];
  }

  interface User {
    id?: number | null;
    nickname?: string | null;
    backendToken?: string | null;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id?: number | null;
    nickname?: string | null;
    backendToken?: string | null;
  }
}
