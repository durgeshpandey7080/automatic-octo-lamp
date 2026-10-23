(() => {
  const tabs = [...document.querySelectorAll('.owner-tabs a')];
  if (!tabs.length) return;
  const active = () => {
    const selected = tabs.some(a => a.hash === location.hash) ? location.hash : '#sales';
    for (const tab of tabs) {
      const current = tab.hash === selected;
      tab.classList.toggle('is-current', current);
      if (current) tab.setAttribute('aria-current', 'location');
      else tab.removeAttribute('aria-current');
    }
  };
  active();
  window.addEventListener('hashchange', active);
})();
