// Integer arithmetic mirrors the server's Decimal calculations, including half-up rounding.
(() => {
  const form = document.getElementById('reading-form');
  if (!form) return;
  const rows = Array.from(form.querySelectorAll('tr[data-fuel]'));
  const parse = (text) => {
    if (!/^\d+(\.\d{0,3})?$/.test(text)) return null;
    const [whole, fraction = ''] = text.split('.');
    return BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, '0'));
  };
  const format = (value, places) => {
    const str = value.toString().padStart(places + 1, '0');
    return str.slice(0, -places) + '.' + str.slice(-places);
  };
  const update = () => {
    let total = 0n, complete = true;
    for (const row of rows) {
      const opening = parse(row.querySelector('[name$="-opening_litres"]').value);
      const closing = parse(row.querySelector('[name$="-closing_litres"]').value);
      const priceInput = form.querySelector('[name="' + row.dataset.fuel.toLowerCase() + '_price"]');
      const price = priceInput ? parse(priceInput.value) : null;
      const litres = opening !== null && closing !== null && closing >= opening ? closing - opening : null;
      const amount = litres !== null && price !== null && price > 0n ? (litres * price + 5000n) / 10000n : null;
      row.querySelector('.litres-preview').textContent = litres === null ? '—' : format(litres, 3);
      row.querySelector('.due-preview').textContent = amount === null ? '—' : format(amount, 2);
      if (amount === null) complete = false;
      else total += amount;
    }
    document.getElementById('preview-total').textContent = complete && rows.length === 8 ? format(total, 2) : '—';
  };
  form.addEventListener('input', update);
  update();
})();
