(() => {
  const source = document.getElementById('id_source');
  if (source) {
    const update = () => {
      for (const id of ['id_shift', 'id_salesperson']) {
        const field = document.getElementById(id);
        if (!field) continue;
        field.disabled = source.value !== 'SHIFT_CASH';
        if (field.disabled) field.value = '';
      }
    };
    source.addEventListener('change', update);
    update();
  }
  const data = document.getElementById('lube-prices');
  if (!data) return;
  const products = JSON.parse(data.textContent);
  const product = document.getElementById('id_product');
  const quantity = document.getElementById('id_quantity');
  const price = document.getElementById('id_unit_price');
  const unit = document.getElementById('lube-unit');
  const preview = document.getElementById('lube-sale-preview');
  const parse = (value, places) => {
    if (!(new RegExp('^\\d+(\\.\\d{0,' + places + '})?$')).test(value)) return null;
    const [whole, fraction = ''] = value.split('.');
    return BigInt(whole) * (10n ** BigInt(places)) + BigInt(fraction.padEnd(places, '0'));
  };
  const calculate = () => {
    const q = parse(quantity.value, 3), p = parse(price.value, 2);
    if (q === null || p === null || q <= 0n || p <= 0n) { preview.textContent = '—'; return; }
    const paise = ((q * p + 500n) / 1000n).toString().padStart(3, '0');
    preview.textContent = paise.slice(0, -2) + '.' + paise.slice(-2);
  };
  const chosen = () => products.find((p) => p.id === product.value);
  product.addEventListener('change', () => {
    const p = chosen();
    if (p) { price.value = p.price; unit.textContent = p.unit; }
    calculate();
  });
  if (chosen()) {
    unit.textContent = chosen().unit;
    if (!price.value) price.value = chosen().price;
  }
  quantity.addEventListener('input', calculate);
  price.addEventListener('input', calculate);
  calculate();
})();
