(() => {
  const $$ = (s) => document.querySelectorAll(s);

  const toggle = document.querySelector('[data-nav-toggle]');
  const nav = document.getElementById('nav');
  const setNav = (open) => {
    toggle.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('open', open);
  };
  toggle.addEventListener('click', () => setNav(!nav.classList.contains('open')));
  nav.addEventListener('click', (e) => { if (e.target.closest('a')) setNav(false); });

  const now = new Date();
  $$('[data-year]').forEach((el) => { el.textContent = now.getFullYear(); });
  $$('[data-years-since]').forEach((el) => { el.textContent = now.getFullYear() - Number(el.dataset.yearsSince); });

  // Opening hours in UK time: [open, close] in minutes, indexed by day (0 = Sunday)
  const hours = [null, [570, 1050], [570, 1050], [570, 1050], [570, 1050], [570, 1050], [600, 780]];
  const fmt = (m) => {
    const h = Math.floor(m / 60), min = m % 60, ampm = h >= 12 ? 'pm' : 'am';
    return `${h % 12 || 12}${min ? ':' + String(min).padStart(2, '0') : ''}${ampm}`;
  };
  const uk = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/London' }));
  const day = uk.getDay(), mins = uk.getHours() * 60 + uk.getMinutes(), today = hours[day];
  let text, open = false;
  if (today && mins >= today[0] && mins < today[1]) {
    open = true;
    text = `Open now · closes at ${fmt(today[1])}`;
  } else {
    let d = day, label;
    if (today && mins < today[0]) label = 'today';
    else {
      do d = (d + 1) % 7; while (!hours[d]);
      label = d === (day + 1) % 7 ? 'tomorrow' : ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d];
    }
    text = `Closed now · opens ${label} at ${fmt(hours[d][0])}`;
  }
  $$('[data-open-status]').forEach((el) => {
    el.textContent = text;
    el.classList.add(open ? 'is-open' : 'is-closed');
  });

  const mapEl = document.querySelector('[data-map]');
  if (mapEl && window.L) {
    const shop = [Number(mapEl.dataset.lat), Number(mapEl.dataset.lng)];
    const radius = Number(mapEl.dataset.radiusMiles) * 1609.344;
    const map = L.map(mapEl, { scrollWheelZoom: false, zoomSnap: 0.25 });
    map.fitBounds(L.latLng(shop).toBounds(radius * 2), { padding: [12, 12] });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    L.circle(shop, {
      radius,
      color: '#4040ff', weight: 2, fillColor: '#c7e0eb', fillOpacity: 0.35,
    }).addTo(map);
    L.circleMarker(shop, { radius: 8, color: '#000', weight: 2, fillColor: '#ff0000', fillOpacity: 1 })
      .addTo(map)
      .bindPopup('<b>Micro-Check Computers</b><br>The Showroom, Longforth Road<br>Wellington TA21 8RQ');
  }

  // Ink finder: match a typed printer model against the hand-checked UK list (assets/ink.js, INK_DATA)
  // plus the larger converted list (assets/ink-db.json), which is fetched the first time someone uses the finder
  const inkForm = document.querySelector('[data-ink-form]');
  if (inkForm && window.INK_DATA) {
    const q = inkForm.querySelector('[data-ink-q]');
    const out = document.querySelector('[data-ink-results]');
    const emailLink = document.querySelector('a[href^="mailto:"]');
    const mail = emailLink ? emailLink.getAttribute('href').split('?')[0] : '';
    const norm = (t) => t.toLowerCase().replace(/[^a-z0-9]/g, '');
    const esc = (t) => t.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    const brands = ['hp', 'canon', 'epson', 'brother', 'samsung'];
    const otherBrands = ['kodak', 'lexmark', 'xerox', 'ricoh', 'kyocera', 'dell', 'oki', 'sharp', 'panasonic', 'konica'];
    const makerFinders = {
      hp: ['HP', 'https://www.hp.com/gb-en/shop/ink-toner-paper'],
      canon: ['Canon', 'https://www.canon.co.uk/store/'],
      epson: ['Epson', 'https://www.epson.co.uk/en_GB/inkfinder'],
      brother: ['Brother', 'https://www.brother.co.uk/supplies'],
    };
    const index = [];
    const known = new Set();
    function add(sets, skipKnown) {
      sets.forEach((set) => set.models.forEach((m) => {
        const full = `${set.brand} ${m}`;
        const key = norm(full);
        if (skipKnown && known.has(key)) return;   // the hand-checked UK entry wins
        known.add(key);
        const code = m.split(' ').reverse().find((w) => /\d/.test(w)) || m.split(' ').pop();   // "2720", "XP-2100", "M402n"
        index.push({ set, model: full, key, code: norm(code) });
      }));
    }
    add(window.INK_DATA, false);
    let bulk = null;
    const loadBulk = () => bulk || (bulk = fetch('assets/ink-db.json').then((r) => r.json()).then((d) => add(d.sets, true)).catch(() => {}));

    function search(text) {
      const t = norm(text);
      if (t.length < 3) return [];
      const words = text.toLowerCase().split(/\s+/).map(norm).filter(Boolean);
      if (otherBrands.includes(words[0])) return [];
      const brand = brands.find((b) => t.startsWith(b));
      const bare = brand ? t.slice(brand.length) : t;
      // whole words of the query, and neighbouring pairs ("XP 4105" -> "xp4105"), compared with each model code
      const parts = words.concat(words.slice(1).map((w, i) => words[i] + w));
      const pool = index.filter((e) => !brand || e.key.startsWith(brand));
      const exact = pool.filter((e) => (bare.length >= 6 && e.key.includes(bare)) || parts.includes(e.code));
      // partial number matches ("3755" in "dj3755e") only when nothing matches exactly
      const hits = exact.length ? exact : pool.filter((e) => parts.some((w) => w.length >= 4 && /\d/.test(w) && e.code.includes(w)));
      // one result per cartridge set, exact model matches first
      const bySet = new Map();
      hits.sort((a, b) => (parts.includes(b.code) - parts.includes(a.code)) || a.model.length - b.model.length).forEach((e) => {
        if (!bySet.has(e.set)) bySet.set(e.set, []);
        bySet.get(e.set).push(e.model);
      });
      return [...bySet.entries()].slice(0, 4);
    }

    function render(text) {
      if (!text) { out.innerHTML = ''; return; }
      const found = search(text);
      if (!found.length) {
        const t = norm(text);
        const maker = Object.keys(makerFinders).find((b) => t.startsWith(b));
        out.innerHTML = `<div class="ink-none"><p><b>We couldn't find "${esc(text)}" in our list.</b> Check the model on the printer, or ask us and we'll look it up.</p><div class="btn-row">` +
          (mail ? `<a class="btn btn-ghost" href="${mail}?subject=${encodeURIComponent('Ink for ' + text)}">Ask us about ink for this printer</a>` : '') +
          (maker ? `<a class="btn btn-ghost" href="${makerFinders[maker][1]}" target="_blank" rel="noopener">${makerFinders[maker][0]}'s own UK ink finder</a>` : '') +
          '</div></div>';
        return;
      }
      out.innerHTML = found.map(([set, models]) => `
        <div class="ink-card">
          <p class="ink-for">${esc(models.slice(0, 3).join(', '))}${models.length > 3 ? ' and similar' : ''}</p>
          <h4>${esc(set.name)}</h4>
          <ul class="ticks">${set.carts.map((c) => `<li>${esc(c)}</li>`).join('')}</ul>
          ${mail ? `<a class="btn btn-ghost" href="${mail}?subject=${encodeURIComponent('Ink: ' + set.name)}&body=${encodeURIComponent('Hi, do you have ' + set.name + ' in stock for my ' + models[0] + '?')}">Check it's in stock</a>` : ''}
        </div>`).join('') +
        '<p class="ink-note">Pop in to buy, or email us to check stock first. XL cartridges cost a little more but print far more pages. Please check the code against your old cartridge before buying.</p>';
    }

    inkForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = q.value.trim();
      if (text && !search(text).length) { out.innerHTML = '<p class="ink-note">Searching…</p>'; await loadBulk(); }
      render(text);
      loadBulk();
    });
    q.addEventListener('focus', loadBulk, { once: true });
    document.querySelectorAll('[data-ink-open]').forEach((a) => a.addEventListener('click', () => setTimeout(() => q.focus(), 300)));
  }
})();
