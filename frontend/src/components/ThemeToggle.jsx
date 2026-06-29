import React from 'react';
import { useTheme } from '../context/ThemeContext';
import { FiSun, FiMoon } from 'react-icons/fi';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="fixed bottom-6 left-6 z-50 p-3.5 rounded-full bg-slate-900/80 dark:bg-slate-100/90 text-slate-100 dark:text-slate-900 shadow-2xl border border-slate-700/50 dark:border-slate-200/80 backdrop-blur-md hover:scale-110 active:scale-95 transition-all duration-200 cursor-pointer flex items-center justify-center"
      title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
    >
      {theme === 'dark' ? (
        <FiSun className="w-5 h-5 text-amber-400" />
      ) : (
        <FiMoon className="w-5 h-5 text-indigo-600" />
      )}
    </button>
  );
}
