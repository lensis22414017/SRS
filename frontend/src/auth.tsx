import { createContext, useContext, useState, ReactNode } from "react";

interface User {
  username: string;
  display_name: string;
  roles: string[];
  organization_id: number | null;
}

interface AuthCtx {
  user: User | null;
  setSession: (token: string, user: User) => void;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("srs_user");
    return raw ? JSON.parse(raw) : null;
  });

  const setSession = (token: string, u: User) => {
    localStorage.setItem("srs_token", token);
    localStorage.setItem("srs_user", JSON.stringify(u));
    setUser(u);
  };
  const logout = () => {
    localStorage.removeItem("srs_token");
    localStorage.removeItem("srs_user");
    setUser(null);
  };
  return <Ctx.Provider value={{ user, setSession, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
