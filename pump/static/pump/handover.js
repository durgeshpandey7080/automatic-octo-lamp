// Preview only. The server re-derives sales and validates every amount on save.
(() => {
  const form = document.getElementById('handover-form');
  if (!form) return;
  const cents = (value) => {
    if (!/^\d+(\.\d{0,2})?$/.test(value)) return null;
    const [whole, fraction = ''] = value.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  };
  const display = (amount) => {
    const value = (amount < 0n ? -amount : amount).toString().padStart(3, '0');
    return (amount < 0n ? '-' : '') + value.slice(0, -2) + '.' + value.slice(-2);
  };
  const expected = cents(form.dataset.expectedSales);
  const update = () => {
    const fields = ['cash_received', 'card', 'paytm_business', 'phonepe_business', 'credit_sales', 'expenses'];
    const values = fields.map((name) => cents(form.elements[name].value));
    const cashOutput = document.getElementById('expected-cash-preview');
    const balance = document.getElementById('handover-balance');
    if (expected === null || values.some((value) => value === null)) {
      cashOutput.textContent = '-';
      balance.textContent = 'Enter valid amounts with up to two decimals in every collection field.';
      balance.className = '';
      return;
    }
    const [cash, card, paytm, phonepe, credit, expenses] = values;
    const adjustmentText = form.dataset.cashAdjustment || '0';
    const adjustment = adjustmentText.startsWith('-') ? -(cents(adjustmentText.slice(1)) || 0n) : (cents(adjustmentText) || 0n);
    const due = expected + adjustment - card - paytm - phonepe - credit - expenses;
    if (due < 0n) {
      cashOutput.textContent = '-';
      balance.textContent = 'Card + Paytm for Business + PhonePe Business + credit sales + expenses exceed recorded sales. Check the amounts.';
      balance.className = 'shortage-text';
      return;
    }
    cashOutput.textContent = display(due);
    const delta = cash - due;
    balance.className = delta < 0n ? 'shortage-text' : delta > 0n ? 'excess-text' : 'balanced-text';
    balance.textContent = delta === 0n ? 'Balanced | cash submitted matches expected cash.' :
      (delta < 0n ? 'Shortage' : 'Excess') + ' | Rs ' + display(delta < 0n ? -delta : delta) +
      ' - add an explanation before saving.';
  };
  form.addEventListener('input', update);
  update();
})();
