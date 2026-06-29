import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function MonthlySpendTrend({ data }) {
  // Expected structure: [{ month: '2026-05', amount: X }, ...]
  const months = (data || []).map((item) => item.month);
  const amounts = (data || []).map((item) => item.amount);

  const chartData = {
    labels: months.length > 0 ? months : ['No Data'],
    datasets: [
      {
        fill: true,
        label: 'Spend ($)',
        data: amounts.length > 0 ? amounts : [0],
        backgroundColor: 'rgba(99, 102, 241, 0.15)', // Indigo gradient fill
        borderColor: '#6366f1',
        borderWidth: 2,
        pointBackgroundColor: '#6366f1',
        pointBorderColor: '#0f172a',
        pointBorderWidth: 1.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.35, // Smooth curves
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#94a3b8',
        bodyColor: '#f1f5f9',
        borderColor: 'rgba(51, 65, 85, 0.5)',
        borderWidth: 1,
        padding: 10,
        callbacks: {
          label: (context) => ` $${context.raw.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
        },
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(51, 65, 85, 0.08)',
        },
        ticks: {
          color: '#94a3b8',
          font: {
            family: 'Inter',
            size: 11,
          },
        },
      },
      y: {
        grid: {
          color: 'rgba(51, 65, 85, 0.08)',
        },
        ticks: {
          color: '#94a3b8',
          font: {
            family: 'Inter',
            size: 11,
          },
          callback: (value) => `$${value}`,
        },
      },
    },
  };

  return (
    <div className="w-full h-full relative" style={{ minHeight: '260px' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}
