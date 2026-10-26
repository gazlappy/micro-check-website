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
})();
