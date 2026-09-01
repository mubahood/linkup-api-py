import React, { createContext, useContext, useState, useCallback } from 'react';

const AppScopeContext = createContext(null);

const KEY = 'admin_app_scope';

export function AppScopeProvider({ children }) {
  const [appId, setAppIdState] = useState(() => localStorage.getItem(KEY) || '');

  const setAppId = useCallback((v) => {
    setAppIdState(v);
    if (v) localStorage.setItem(KEY, v); else localStorage.removeItem(KEY);
  }, []);

  return (
    <AppScopeContext.Provider value={{ appId, setAppId }}>
      {children}
    </AppScopeContext.Provider>
  );
}

// appId: '' (all apps) | 'linkup' | 'abanoonya' | 'uganda_dating'
export function useAppScope() {
  return useContext(AppScopeContext);
}

export const APP_LABELS = {
  '': 'All Apps',
  linkup: 'LinkUp',
  abanoonya: 'Abanoonya Pro',
  uganda_dating: 'Uganda Dating App',
};
