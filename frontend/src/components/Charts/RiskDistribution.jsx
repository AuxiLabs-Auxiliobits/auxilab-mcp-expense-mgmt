import React from 'react';
import { Doughnut } from 'react-chartjs-2';
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

export default function RiskDistribution({ data }) {
  // Expected structure: [{ bucket: 'Low (0-35)', count: X }, ...]
  const buckets = (data || []).map((item) => item.bucket);
  const counts = (data || []).map((item) => item.count);

  const chartData = {
    labels: buckets.length > 0 ? buckets : ['Low', 'Medium', 'High'],
    datasets: [
      {
        data: counts.length > 0 ? counts : [0, 0, 0],
        backgroundColor: [
          'rgba(16, 185, 129, 0.65)',  // Emerald (Low)
          'rgba(245, 158, 11, 0.65)',  // Amber (Medium)
          'rgba(239, 68, 68, 0.65)',   // Rose (High)
        ],
        borderColor: [
          '#10b981',
          '#f59e0b',
          '#ef4444',
        ],
        borderWidth: 1.5,
        hoverOffset: 4,
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
    cutout: '70%', // Donut feel
  };

  return (
    <div className="w-full h-full flex items-center justify-center relative" style={{ minHeight: '260px' }}>
      <Doughnut data={chartData} options={options} />
    </div>
  );
}
