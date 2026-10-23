(() => {
 const trigger=document.querySelector('.menu-toggle');
 const backdrop=document.querySelector('.nav-backdrop');
 const sidebar=document.querySelector('.sidebar');
 const media=window.matchMedia('(max-width:800px)');
 const sync=()=>{if(sidebar)sidebar.inert=media.matches&&!document.body.classList.contains('nav-open');};
 const close=()=>{document.body.classList.remove('nav-open'); if(trigger)trigger.setAttribute('aria-expanded','false'); if(backdrop)backdrop.hidden=true;sync();};
 if(trigger)trigger.addEventListener('click',()=>{const open=!document.body.classList.contains('nav-open');document.body.classList.toggle('nav-open',open);trigger.setAttribute('aria-expanded',String(open));backdrop.hidden=!open;sync();if(open)sidebar.querySelector('a').focus();});
 if(backdrop)backdrop.addEventListener('click',close);
 media.addEventListener('change',()=>{close();sync();});sync();
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){close();if(trigger)trigger.focus();}});
 document.querySelectorAll('.sidebar a').forEach(a=>a.addEventListener('click',close));
 const active=()=>{document.querySelectorAll('.nav-link[data-section]').forEach(a=>{const url=new URL(a.href);a.classList.toggle('active',url.pathname===location.pathname && (location.hash||'#overview')===url.hash);});document.querySelectorAll('.nav-link').forEach(a=>{if(a.classList.contains('active'))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});};
 active();window.addEventListener('hashchange',active);
})();
