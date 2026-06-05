import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import axios from 'axios';

// ─── Types ───────────────────────────────────────────────────────────────────

interface User {
  sub: string;
  role: 'viewer' | 'operator' | 'admin';
  exp: number;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  role: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (minRole: 'viewer' | 'operator' | 'admin') => boolean;
}

// ─── Role Hierarchy ───────────────────────────────────────────────────────────

const ROLE_LEVELS: Record<'viewer' | 'operator' | 'admin', number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
};

// ─── JWT Helpers ──────────────────────────────────────────────────────────────

/**
 * Decodes the payload of a JWT (no signature verification — done server-side).
 * Returns null if the token is malformed.
 */
function decodeJwtPayload(token: string): User | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // Base64url → Base64 → decode
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const jsonStr = atob(padded);
    const payload = JSON.parse(jsonStr) as Partial<User>;
    if (!payload.sub || !payload.role || !payload.exp) return null;
    return payload as User;
  } catch {
    return null;
  }
}

/**
 * Returns true if the decoded JWT has not yet expired.
 */
function isTokenValid(user: User): boolean {
  return user.exp * 1000 > Date.now();
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = 'aios_token';

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  // On mount: attempt to restore session from localStorage
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (!storedToken) return;

    const decoded = decodeJwtPayload(storedToken);
    if (decoded && isTokenValid(decoded)) {
      setToken(storedToken);
      setUser(decoded);
      // Attach to axios globally
      axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
    } else {
      // Token expired — clear storage
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  /**
   * Authenticates the user against /api/auth/login.
   * On success, stores the JWT and sets user state.
   */
  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const response = await axios.post<{ token: string }>('/api/auth/login', {
      email,
      password,
    });

    const { token: newToken } = response.data;
    const decoded = decodeJwtPayload(newToken);
    if (!decoded) throw new Error('Received an invalid token from server.');
    if (!isTokenValid(decoded)) throw new Error('Received an expired token from server.');

    localStorage.setItem(TOKEN_KEY, newToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
    setToken(newToken);
    setUser(decoded);
  }, []);

  /**
   * Clears the session from state and localStorage.
   */
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    delete axios.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
  }, []);

  /**
   * Returns true if the current user's role is at least `minRole`.
   */
  const hasRole = useCallback(
    (minRole: 'viewer' | 'operator' | 'admin'): boolean => {
      if (!user) return false;
      return ROLE_LEVELS[user.role] >= ROLE_LEVELS[minRole];
    },
    [user],
  );

  const value: AuthContextType = {
    user,
    token,
    role: user?.role ?? null,
    isAuthenticated: user !== null && token !== null,
    login,
    logout,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuthContext(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuthContext must be used within an <AuthProvider>');
  }
  return ctx;
}
