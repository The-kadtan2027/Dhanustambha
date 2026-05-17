import { useState, useEffect } from 'react';

const STORAGE_KEY = 'dhanustambha_account_size';
const DEFAULT_SIZE = 500_000;

/**
 * Shared hook that reads/writes account size from localStorage.
 * Any component using this hook will stay in sync with the Sidebar input
 * because they share the same localStorage key.
 */
export function useAccountSize(): [number, (val: number) => void] {
  const [accountSize, setAccountSizeState] = useState<number>(DEFAULT_SIZE);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setAccountSizeState(Number(saved));
  }, []);

  const setAccountSize = (val: number) => {
    setAccountSizeState(val);
    localStorage.setItem(STORAGE_KEY, val.toString());
  };

  return [accountSize, setAccountSize];
}
