// @ai-generated (offline fallback)
export function calculateLoan(amount, rate, term) {
  const monthlyRate = rate / 100 / 12;
  const payment = (amount * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -term));
  return { monthlyPayment: Number(payment.toFixed(2)), total: Number((payment * term).toFixed(2)) };
}
