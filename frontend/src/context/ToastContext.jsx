import React, { createContext, useContext, useState, useCallback } from 'react';
import { FiCheckCircle, FiAlertCircle, FiInfo, FiX } from 'react-icons/fi';

const ToastContext = createContext();

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      
      {/* Toast Container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <Toast 
            key={toast.id} 
            toast={toast} 
            onClose={() => removeToast(toast.id)} 
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function Toast({ toast, onClose }) {
  const { message, type } = toast;

  const config = {
    success: {
      bg: 'bg-emerald-500/15',
      border: 'border-emerald-500/30',
      icon: <FiCheckCircle className="w-5 h-5 text-emerald-400" />,
      text: 'text-emerald-400'
    },
    error: {
      bg: 'bg-rose-500/15',
      border: 'border-rose-500/30',
      icon: <FiAlertCircle className="w-5 h-5 text-rose-400" />,
      text: 'text-rose-400'
    },
    info: {
      bg: 'bg-blue-500/15',
      border: 'border-blue-500/30',
      icon: <FiInfo className="w-5 h-5 text-blue-400" />,
      text: 'text-blue-400'
    }
  }[type] || config.info;

  return (
    <div className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border backdrop-blur-md shadow-xl animate-fade-in-up w-80 ${config.bg} ${config.border}`}>
      <div className="shrink-0 mt-0.5">{config.icon}</div>
      <div className={`flex-1 text-sm font-medium ${config.text} leading-snug`}>
        {message}
      </div>
      <button 
        onClick={onClose}
        className={`shrink-0 p-1 rounded-md opacity-70 hover:opacity-100 hover:bg-slate-800/30 transition-all ${config.text}`}
      >
        <FiX className="w-4 h-4" />
      </button>
    </div>
  );
}
