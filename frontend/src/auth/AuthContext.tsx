import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, tokenStore, AUTH_EXPIRED_EVENT } from '@/lib/api';
import type { SignupInput, User } from '@/lib/types';

interface AuthValue {
  user: User | null;
  /** true while we're still deciding whether there's a valid session */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const hasToken = tokenStore.get() !== null;

  const { data, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get<User>('/users/me'),
    enabled: hasToken,
    retry: false,
    staleTime: 60_000,
  });

  const logout = useCallback(() => {
    tokenStore.clear();
    qc.clear();
    qc.setQueryData(['me'], null);
  }, [qc]);

  useEffect(() => {
    const onExpired = () => {
      qc.clear();
      qc.setQueryData(['me'], null);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [qc]);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await api.login(email, password);
      tokenStore.set(token);
      return qc.fetchQuery({ queryKey: ['me'], queryFn: () => api.get<User>('/users/me'), staleTime: 0 });
    },
    [qc],
  );

  const signup = useCallback(async (input: SignupInput) => {
    await api.post<User>('/auth/signup', input);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user: tokenStore.get() ? (data ?? null) : null,
      loading: hasToken && isLoading,
      login,
      signup,
      logout,
    }),
    [data, hasToken, isLoading, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
