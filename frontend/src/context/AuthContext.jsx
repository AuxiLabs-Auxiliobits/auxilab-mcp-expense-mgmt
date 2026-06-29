import React, { createContext, useContext, useState, useEffect } from 'react';
import { login as apiLogin, fetchMe } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('expenseops_token');
      if (token) {
        try {
          const profile = await fetchMe();
          setUser(profile);
        } catch (err) {
          console.error("Session expired or invalid", err);
          localStorage.removeItem('expenseops_token');
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email, password) => {
    const data = await apiLogin(email, password);
    localStorage.setItem('expenseops_token', data.access_token);
    const profile = await fetchMe();
    setUser(profile);
  };

  const logout = () => {
    localStorage.removeItem('expenseops_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
