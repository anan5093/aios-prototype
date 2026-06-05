import { useAuthContext } from '../context/AuthContext';

/**
 * Thin convenience hook that returns the full AuthContext value.
 * Prefer `useAuth()` over importing `useAuthContext` directly in components.
 */
export function useAuth() {
  return useAuthContext();
}
