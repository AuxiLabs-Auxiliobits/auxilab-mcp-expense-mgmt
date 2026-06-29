import React from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

// Register necessary Chart.js elements
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

export default function SpendByCategory({ data }) {
  const categories = Object.keys(data || {});
  const spendValues = Object.values(data || {});

  const chartData = {
    labels: categories.length > 0 ? categories : ['No Data'],
    datasets: [
      {
        label: 'Spend ($)',
        data: spendValues.length > 0 ? spendValues : [0],
        backgroundColor: 'rgba(45, 212, 191, 0.65)', // Teal gradient color
        borderColor: '#2dd4bf',
        borderWidth: 1.5,
        borderRadius: 6,
        hoverBackgroundColor: 'rgba(45, 212, 191, 0.85)',
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false, // Hide legend for single dataset bar chart
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
          color: 'rgba(51, 65, 85, 0.15)',
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
          color: 'rgba(51, 65, 85, 0.15)',
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
      <Bar data={chartData} options={options} />
    </div>
  );
}
