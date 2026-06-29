import React from 'react';
import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  ArcElement,
  Tooltip,
  Legend
);

const STATUS_LABELS = {
  APPROVED: 'Approved',
  PENDING: 'Pending',
  REJECTED: 'Rejected',
  EXCEPTION_HOLD: 'Exception Hold',
  ESCALATED: 'Escalated',
};

const COLOR_MAP = {
  APPROVED: 'rgba(16, 185, 129, 0.65)',     // Emerald
  PENDING: 'rgba(245, 158, 11, 0.65)',      // Amber
  REJECTED: 'rgba(239, 68, 68, 0.65)',      // Rose
  EXCEPTION_HOLD: 'rgba(249, 115, 22, 0.65)',// Orange
  ESCALATED: 'rgba(139, 92, 246, 0.65)',     // Violet
};

const BORDER_MAP = {
  APPROVED: '#10b981',
  PENDING: '#f59e0b',
  REJECTED: '#ef4444',
  EXCEPTION_HOLD: '#f97316',
  ESCALATED: '#8b5cf6',
};

export default function ApprovalStatusPie({ data }) {
  // Expected structure: { APPROVED: X, PENDING: Y, ... }
  const rawStatuses = Object.keys(data || {});
  const counts = Object.values(data || {});

  const labels = rawStatuses.map(s => STATUS_LABELS[s] || s);
  const backgroundColors = rawStatuses.map(s => COLOR_MAP[s] || 'rgba(148, 163, 184, 0.65)');
  const borderColors = rawStatuses.map(s => BORDER_MAP[s] || '#94a3b8');

  const chartData = {
    labels: labels.length > 0 ? labels : ['No Data'],
    datasets: [
      {
        data: counts.length > 0 ? counts : [0],
        backgroundColor: backgroundColors.length > 0 ? backgroundColors : ['#334155'],
        borderColor: borderColors.length > 0 ? borderColors : ['#475569'],
        borderWidth: 1.5,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right',
        labels: {
          color: '#94a3b8',
          font: {
            family: 'Inter',
            size: 11,
          },
          padding: 12,
        },
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#94a3b8',
        bodyColor: '#f1f5f9',
        borderColor: 'rgba(51, 65, 85, 0.5)',
        borderWidth: 1,
        padding: 10,
      },
    },
  };

  return (
    <div className="w-full h-full flex items-center justify-center relative" style={{ minHeight: '260px' }}>
      <Pie data={chartData} options={options} />
    </div>
  );
}
