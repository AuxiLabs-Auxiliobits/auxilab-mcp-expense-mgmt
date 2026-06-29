export const rupees = (n) =>
  typeof n === 'number' ? `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—';

export const humanizeCategory = (cat) =>
  cat ? cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : '—';
