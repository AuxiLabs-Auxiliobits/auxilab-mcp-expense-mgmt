import { useState, useEffect, useRef } from 'react';
import { FiDollarSign, FiCheckCircle, FiAlertTriangle, FiShield } from 'react-icons/fi';

function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 0, duration = 1200 }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);
  const startTime = useRef(null);

  useEffect(() => {
    startTime.current = performance.now();
    const animate = (now) => {
      const elapsed = now - startTime.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(eased * value);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  const formatted = decimals > 0
    ? display.toFixed(decimals)
    : Math.round(display).toLocaleString();

  return (
    <span className="font-mono tabular-nums">
      {prefix}{formatted}{suffix}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, prefix, suffix, decimals, change, changeLabel, color, delay }) {
  const colorMap = {
    teal: { iconBg: 'bg-teal-500/15', iconText: 'text-teal-400', border: 'border-teal-500/20' },
    emerald: { iconBg: 'bg-emerald-500/15', iconText: 'text-emerald-400', border: 'border-emerald-500/20' },
    amber: { iconBg: 'bg-amber-500/15', iconText: 'text-amber-400', border: 'border-amber-500/20' },
    rose: { iconBg: 'bg-rose-500/15', iconText: 'text-rose-400', border: 'border-rose-500/20' },
  };
  const c = colorMap[color] || colorMap.teal;

  const isPositiveGood = label === 'Auto-Pass Rate';
  const isNegativeGood = label === 'Pending Exceptions' || label === 'Avg Risk Score';

  let changeColor = 'text-slate-400';
  if (change !== undefined && change !== null) {
    if (isPositiveGood) {
      changeColor = change > 0 ? 'text-emerald-400' : 'text-rose-400';
    } else if (isNegativeGood) {
      changeColor = change < 0 ? 'text-emerald-400' : 'text-rose-400';
    } else {
      changeColor = change > 0 ? 'text-rose-400' : 'text-emerald-400';
    }
  }

  return (
    <div
      className="glass-card glass-card-hover p-6 animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`p-3 rounded-xl ${c.iconBg}`}>
          <Icon className={`w-6 h-6 ${c.iconText}`} />
        </div>
        {change !== undefined && change !== null && (
          <span className={`text-sm font-semibold ${changeColor} flex items-center gap-1`}>
            {change > 0 ? '↑' : '↓'} {Math.abs(change)}{suffix === '%' ? 'pp' : '%'}
          </span>
        )}
      </div>
      <div className="text-3xl font-bold text-slate-100 mb-1 animate-count-up">
        <AnimatedNumber value={value} prefix={prefix} suffix={suffix} decimals={decimals} />
      </div>
      <div className="text-sm text-slate-400 font-medium">{label}</div>
      {changeLabel && (
        <div className="text-xs text-slate-500 mt-1">{changeLabel}</div>
      )}
    </div>
  );
}

export default function MetricsRibbon({ metrics, loading }) {
  if (loading || !metrics) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="glass-card p-6 h-32">
            <div className="flex items-start justify-between mb-4">
              <div className="w-12 h-12 rounded-xl animate-shimmer" />
              <div className="w-16 h-5 rounded animate-shimmer" />
            </div>
            <div className="w-32 h-9 rounded animate-shimmer mb-2" />
            <div className="w-24 h-4 rounded animate-shimmer" />
          </div>
        ))}
      </div>
    );
  }

  const metricConfigs = [
    {
      id: "spend",
      icon: FiDollarSign,
      label: "Total Spend Volume",
      value: metrics.total_amount || 0,
      prefix: "$",
      decimals: 0,
      change: metrics.spend_change,
      changeLabel: `vs. last ${metrics.period || 'period'}`,
      color: "teal",
      delay: 0
    },
    {
      id: "pass_rate",
      icon: FiCheckCircle,
      label: "Auto-Pass Rate",
      value: metrics.auto_pass_rate || 0,
      suffix: "%",
      decimals: 1,
      change: metrics.pass_rate_change,
      changeLabel: "approval automation",
      color: "emerald",
      delay: 100
    },
    {
      id: "exceptions",
      icon: FiAlertTriangle,
      label: "Pending Exceptions",
      value: metrics.pending_count || 0,
      decimals: 0,
      change: metrics.exceptions_change,
      changeLabel: "requires review",
      color: "amber",
      delay: 200
    },
    {
      id: "risk",
      icon: FiShield,
      label: "Avg Risk Score",
      value: metrics.avg_risk_score || 0,
      decimals: 1,
      change: metrics.risk_change,
      changeLabel: "across all claims",
      color: "rose",
      delay: 300
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
      {metricConfigs.map((config) => (
        <MetricCard key={config.id} {...config} />
      ))}
    </div>
  );
}
