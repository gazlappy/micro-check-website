(function () {
  var doc = document, root = doc.documentElement, body = doc.body;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var isPhone = function () { return window.matchMedia('(max-width: 760px)').matches; };
  var $ = function (s, el) { return (el || doc).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); };
  var store = {
    get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  var PHONE = '01823 664943', TEL = 'tel:+441823664943';

  root.classList.add('js');

  // ---------- Clock and opening hours ----------
  // Minutes since midnight, UK time. 0 = Sunday.
  var HOURS = { 1: [570, 1050], 2: [570, 1050], 3: [570, 1050], 4: [570, 1050], 5: [570, 1050], 6: [600, 780] };
  var DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  function fmt(mins) {
    var h = Math.floor(mins / 60), m = mins % 60;
    return ((h + 11) % 12 + 1) + (m ? ':' + String(m).padStart(2, '0') : '') + (h < 12 ? 'am' : 'pm');
  }

  function shopStatus() {
    var parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/London', weekday: 'long', hour: 'numeric', minute: 'numeric', hour12: false
    }).formatToParts(new Date());
    var get = function (t) { return parts.find(function (p) { return p.type === t; }).value; };
    var day = DAYS.indexOf(get('weekday'));
    var now = (parseInt(get('hour'), 10) % 24) * 60 + parseInt(get('minute'), 10);
    var today = HOURS[day];
    if (today && now >= today[0] && now < today[1]) return { open: true, text: 'Open now · closes ' + fmt(today[1]) };
    if (today && now < today[0]) return { open: false, text: 'Closed · opens ' + fmt(today[0]) + ' today' };
    for (var i = 1; i <= 7; i++) {
      var d = (day + i) % 7;
      if (HOURS[d]) return { open: false, text: 'Closed · opens ' + fmt(HOURS[d][0]) + ' ' + (i === 1 ? 'tomorrow' : DAYS[d]) };
    }
  }

  function tick() {
    var now = new Date();
    var time = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    $$('[data-clock]').forEach(function (el) { el.textContent = time; });
    $$('[data-date]').forEach(function (el) { el.textContent = now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }); });
    $$('[data-date-short]').forEach(function (el) { el.textContent = now.toLocaleDateString('en-GB'); });
    try {
      var s = shopStatus();
      $$('[data-open-status]').forEach(function (el) {
        el.textContent = s.text;
        el.classList.toggle('is-open', s.open);
        el.classList.toggle('is-closed', !s.open);
      });
    } catch (e) { /* leave the static text */ }
  }
  tick();
  setInterval(tick, 15000);

  $$('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });
  $$('[data-years-since]').forEach(function (el) {
    el.textContent = new Date().getFullYear() - parseInt(el.getAttribute('data-years-since'), 10);
  });

  // ---------- Window manager ----------
  var wins = {}, z = 10, placed = 0, active = null;
  var taskBox = $('[data-tasks]');

  $$('.window').forEach(function (el) {
    var id = el.id;
    var ico = $('.dicon[data-open="' + id + '"] .app-ico');
    var bar = doc.createElement('header');
    bar.className = 'titlebar';
    bar.innerHTML =
      '<button type="button" class="back" data-close aria-label="Back">‹</button>' +
      (ico ? ico.outerHTML : '') +
      '<span class="ttl"></span>' +
      '<span class="wctl">' +
      '<button type="button" data-min aria-label="Minimise">–</button>' +
      '<button type="button" data-max aria-label="Maximise">▢</button>' +
      '<button type="button" data-close aria-label="Close">✕</button></span>';
    $('.ttl', bar).textContent = el.getAttribute('data-title');
    el.insertBefore(bar, el.firstChild);
    el.hidden = true;
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', el.getAttribute('data-title'));
    wins[id] = { el: el, bar: bar, ico: ico ? ico.outerHTML : '', task: null };
    drag(el, bar);
    bar.addEventListener('dblclick', function (e) {
      if (!e.target.closest('button')) el.classList.toggle('max');
    });
    el.addEventListener('pointerdown', function () { focus(id); });
  });

  function setHash(id) {
    try { history.replaceState(null, '', id ? '#' + id : location.pathname + location.search); } catch (e) { /* file:// */ }
  }

  function focus(id) {
    active = id;
    Object.keys(wins).forEach(function (k) {
      wins[k].el.classList.toggle('active', k === id);
      if (wins[k].task) wins[k].task.classList.toggle('active', k === id);
    });
    if (id) wins[id].el.style.zIndex = ++z;
  }

  function openWin(id) {
    var w = wins[id];
    if (!w) return;
    var el = w.el;
    if (!el.dataset.placed) {
      var width = Math.min(parseInt(el.getAttribute('data-w') || '640', 10), window.innerWidth - 24);
      var off = (placed++ % 6) * 30;
      el.style.width = width + 'px';
      el.style.left = Math.max(12, Math.round((window.innerWidth - width) / 2) - 60 + off) + 'px';
      el.style.top = (24 + off) + 'px';
      el.dataset.placed = '1';
    }
    if (isPhone()) {
      // one app at a time on a phone
      Object.keys(wins).forEach(function (k) {
        if (k === id || wins[k].el.hidden) return;
        wins[k].el.hidden = true;
        if (wins[k].task) { wins[k].task.remove(); wins[k].task = null; }
      });
    }
    el.hidden = false;
    el.classList.remove('min');
    $$('iframe[data-src]', el).forEach(function (f) { f.src = f.getAttribute('data-src'); f.removeAttribute('data-src'); });
    if (!w.task) {
      var t = doc.createElement('button');
      t.type = 'button';
      t.className = 'task';
      t.innerHTML = w.ico + '<span></span>';
      t.lastChild.textContent = el.getAttribute('data-title');
      t.addEventListener('click', function () {
        if (active === id && !el.classList.contains('min')) minWin(id); else openWin(id);
      });
      taskBox.appendChild(t);
      w.task = t;
    }
    active = null;
    focus(id);
    setHash(id);
    if (id === 'terminal' && !isPhone()) { var inp = $('#cmd'); if (inp) inp.focus(); }
  }

  function topWin() {
    var best = null, bz = -1;
    Object.keys(wins).forEach(function (k) {
      var el = wins[k].el;
      if (!el.hidden && !el.classList.contains('min') && (parseInt(el.style.zIndex, 10) || 0) > bz) {
        bz = parseInt(el.style.zIndex, 10) || 0; best = k;
      }
    });
    return best;
  }

  function closeWin(id) {
    var w = wins[id];
    w.el.hidden = true;
    w.el.classList.remove('max');
    if (w.task) { w.task.remove(); w.task = null; }
    active = null;
    var next = topWin();
    focus(next);
    setHash(next);
  }

  function minWin(id) {
    wins[id].el.classList.add('min');
    active = null;
    focus(topWin());
  }

  function drag(el, bar) {
    var sx, sy, ox, oy, on = false;
    bar.addEventListener('pointerdown', function (e) {
      if (e.target.closest('button') || isPhone() || el.classList.contains('max') || e.button > 0) return;
      on = true; sx = e.clientX; sy = e.clientY; ox = el.offsetLeft; oy = el.offsetTop;
      bar.setPointerCapture(e.pointerId);
      el.classList.add('dragging');
    });
    bar.addEventListener('pointermove', function (e) {
      if (!on) return;
      var x = ox + e.clientX - sx, y = oy + e.clientY - sy;
      el.style.left = Math.min(window.innerWidth - 90, Math.max(90 - el.offsetWidth, x)) + 'px';
      el.style.top = Math.min(window.innerHeight - 100, Math.max(0, y)) + 'px';
    });
    var end = function () { on = false; el.classList.remove('dragging'); };
    bar.addEventListener('pointerup', end);
    bar.addEventListener('pointercancel', end);
  }

  // ---------- Start menu, global clicks ----------
  var startBtn = $('[data-start]'), startMenu = $('[data-startmenu]');
  function toggleStart(show) {
    startMenu.hidden = show === undefined ? !startMenu.hidden : !show;
    startBtn.setAttribute('aria-expanded', String(!startMenu.hidden));
  }

  doc.addEventListener('click', function (e) {
    var t = e.target;
    var opener = t.closest('[data-open]');
    if (opener) {
      e.preventDefault();
      var tab = opener.getAttribute('data-tab-target');
      openWin(opener.getAttribute('data-open'));
      if (tab) selectTab(tab);
    }
    var ctl = t.closest('[data-close],[data-min],[data-max]');
    var win = ctl && ctl.closest('.window');
    if (win) {
      if (ctl.hasAttribute('data-close')) closeWin(win.id);
      else if (ctl.hasAttribute('data-min')) minWin(win.id);
      else win.classList.toggle('max');
    }
    if (!ctx.hidden) ctx.hidden = true;
    if (t.closest('[data-start]')) toggleStart();
    else if (!t.closest('[data-startmenu]') || opener) toggleStart(false);
  });

  doc.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (!startMenu.hidden) toggleStart(false);
    else if (active) closeWin(active);
  });

  window.addEventListener('hashchange', function () {
    var id = location.hash.slice(1);
    if (wins[id] && active !== id) openWin(id);
  });

  // Wallpaper
  var WP = 5;
  try { body.dataset.wp = localStorage.getItem('mc-wallpaper') || '0'; } catch (e) { /* ignore */ }
  $$('[data-wallpaper]').forEach(function (b) {
    b.addEventListener('click', function () {
      var n = String((parseInt(body.dataset.wp, 10) + 1) % WP);
      body.dataset.wp = n;
      try { localStorage.setItem('mc-wallpaper', n); } catch (e) { /* ignore */ }
    });
  });

  // Right-click menu on the desktop
  var ctx = $('[data-ctx]');
  $('.desktop').addEventListener('contextmenu', function (e) {
    if (isPhone() || e.target.closest('.window, a, input, textarea')) return;
    e.preventDefault();
    ctx.hidden = false;
    ctx.style.left = Math.min(e.clientX, window.innerWidth - ctx.offsetWidth - 8) + 'px';
    ctx.style.top = Math.min(e.clientY, window.innerHeight - ctx.offsetHeight - 60) + 'px';
  });
  $('[data-refresh]').addEventListener('click', function () {
    var icons = $('.icons');
    icons.classList.remove('refresh'); void icons.offsetWidth; icons.classList.add('refresh');
  });

  // Start menu search
  var smSearch = $('[data-sm-search]');
  smSearch.addEventListener('input', function () {
    var q = smSearch.value.trim().toLowerCase();
    $$('.sm-grid a').forEach(function (a) { a.hidden = q && a.textContent.toLowerCase().indexOf(q) < 0; });
  });
  smSearch.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var first = $('.sm-grid a:not([hidden])');
    if (first) first.click();
  });
  startBtn.addEventListener('click', function () {
    smSearch.value = '';
    smSearch.dispatchEvent(new Event('input'));
    setTimeout(function () { if (!startMenu.hidden && !isPhone()) smSearch.focus(); }, 0);
  });

  // ---------- Boot and shut down ----------
  var bootEl = $('#boot'), offEl = $('#off');
  var BOOT = [
    'Micro-Check BIOS v19.98   (c) Wellington, Somerset',
    '',
    'Memory test ............... 640K (ought to be enough for anybody)',
    'Detecting customers ....... 1 found',
    'Loading plain English ..... done',
    'Loading jargon drivers .... not installed',
    'Checking kettle ........... on',
    '',
    'Starting Micro-Check OS ...'
  ];

  function boot(done) {
    var pre = $('[data-boot]'), i = 0, finished = false, timer;
    pre.textContent = '';
    bootEl.classList.remove('out');
    bootEl.hidden = false;
    var finish = function () {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      doc.removeEventListener('keydown', finish);
      bootEl.removeEventListener('click', finish);
      bootEl.classList.add('out');
      setTimeout(function () { bootEl.hidden = true; }, 360);
      done();
    };
    var step = function () {
      if (i >= BOOT.length) { timer = setTimeout(finish, 450); return; }
      pre.textContent += BOOT[i++] + '\n';
      timer = setTimeout(step, 230);
    };
    doc.addEventListener('keydown', finish);
    bootEl.addEventListener('click', finish);
    step();
  }

  $('[data-shutdown]').addEventListener('click', function () { toggleStart(false); offEl.hidden = false; });
  $('[data-poweron]').addEventListener('click', function () { offEl.hidden = true; boot(function () {}); });

  function startDesktop() {
    var want = location.hash.slice(1);
    if (wins[want]) openWin(want);
    else if (!isPhone()) openWin('welcome');
    if (!store.get('mc-chip') && !isPhone()) {
      setTimeout(function () {
        if (active === 'finder' || active === 'game') return;
        showTip(0);
        store.set('mc-chip', '1');
      }, 9000);
    }
  }

  // ---------- Chip, the helper ----------
  var TIPS = [
    ['Hi, I\'m Chip. It looks like you\'re trying to fix a computer. Would you like help?', 'Find my fault', 'finder'],
    ['Did you know? Swapping an old hard drive for an SSD can make a tired laptop feel new.', 'What\'s an SSD?', 'jargon'],
    ['Buying a new computer? Tell me what it\'s for and I\'ll suggest a spec.', 'Open PC Picker', 'picker'],
    ['Curious what your own device is made of? I can have a look.', 'Check this device', 'sysinfo'],
    ['Write down what\'s wrong before you forget the details.', 'Write a repair note', 'book'],
    ['All work and no play. There are viruses that need zapping.', 'Play Virus Zapper', 'game'],
    ['Try right-clicking the desktop. Or leave me alone for a minute and see what happens.', 'Open Terminal', 'terminal']
  ];
  var bubble = $('[data-bubble]'), tipIndex = -1;
  function showTip(i) {
    tipIndex = i % TIPS.length;
    $('[data-bubble-text]').textContent = TIPS[tipIndex][0];
    var link = $('[data-bubble-link]');
    link.textContent = TIPS[tipIndex][1] + ' →';
    link.setAttribute('data-open', TIPS[tipIndex][2]);
    link.setAttribute('href', '#' + TIPS[tipIndex][2]);
    bubble.hidden = false;
    bubble.style.animation = 'none'; void bubble.offsetWidth; bubble.style.animation = '';
  }
  $('[data-buddy-face]').addEventListener('click', function () { showTip(tipIndex + 1); });
  $('[data-bubble-close]').addEventListener('click', function () { bubble.hidden = true; });
  $('[data-bubble-link]').addEventListener('click', function () { bubble.hidden = true; });
  doc.addEventListener('pointermove', function (e) {
    var face = $('[data-buddy-face]'), r = face.getBoundingClientRect();
    if (!r.width) return;
    var dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
    var d = Math.sqrt(dx * dx + dy * dy) || 1;
    $$('.pupil', face).forEach(function (p) {
      p.style.transform = 'translate(' + (dx / d * 1.6).toFixed(2) + 'px,' + (dy / d * 1.6).toFixed(2) + 'px)';
    });
  });

  // ---------- Screensaver ----------
  var saver = $('#saver'), saverLogo = $('[data-saver-logo]'), idleTimer, raf;
  function stopSaver() {
    if (saver.hidden) return;
    saver.hidden = true;
    cancelAnimationFrame(raf);
  }
  function startSaver() {
    if (!saver.hidden || !bootEl.hidden || !offEl.hidden) return;
    saver.hidden = false;
    var x = 40, y = 40, vx = 2.2, vy = 1.7, hue = 0;
    var frame = function () {
      var maxX = window.innerWidth - saverLogo.offsetWidth, maxY = window.innerHeight - saverLogo.offsetHeight;
      x += vx; y += vy;
      if (x <= 0 || x >= maxX) { vx = -vx; x = Math.max(0, Math.min(maxX, x)); hue += 70; }
      if (y <= 0 || y >= maxY) { vy = -vy; y = Math.max(0, Math.min(maxY, y)); hue += 70; }
      saverLogo.style.transform = 'translate(' + x + 'px,' + y + 'px)';
      saverLogo.style.filter = 'hue-rotate(' + hue + 'deg)';
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
  }
  function resetIdle() {
    clearTimeout(idleTimer);
    if (!isPhone() && !reduced) idleTimer = setTimeout(startSaver, 75000);
  }
  var saverArmed = 0;
  ['pointermove', 'pointerdown', 'keydown', 'wheel'].forEach(function (ev) {
    doc.addEventListener(ev, function () {
      if (Date.now() > saverArmed) stopSaver();
      resetIdle();
    }, { passive: true });
  });
  $('[data-saver]').addEventListener('click', function () {
    saverArmed = Date.now() + 800;
    startSaver();
  });
  resetIdle();

  if (reduced || store.get('mc-booted') || location.hash.length > 1) startDesktop();
  else { store.set('mc-booted', '1'); boot(startDesktop); }

  // ---------- Services tabs ----------
  var tabNav = $('[data-tabs]'), panes = $$('.panes article');
  function selectTab(id) {
    panes.forEach(function (p) { p.classList.toggle('on', p.id === id); });
    $$('button', tabNav).forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.id === id)); });
    var box = $('.panes'); if (box) box.scrollTop = 0;
  }
  panes.forEach(function (p) {
    var b = doc.createElement('button');
    b.type = 'button';
    b.dataset.id = p.id;
    var svg = $('h3 .icon', p);
    b.innerHTML = (svg ? svg.outerHTML : '') + '<span></span>';
    b.lastChild.textContent = p.getAttribute('data-tab');
    b.addEventListener('click', function () { selectTab(p.id); });
    tabNav.appendChild(b);
  });
  if (panes.length) selectTab(panes[0].id);

  // ---------- Fault finder ----------
  var finder = $('[data-finder]');
  if (finder) {
    var SLOW = ['It\'s really slow',
      'Usually an ageing hard drive, not enough memory, or years of startup programs and clutter.',
      'A health check and clean-up, and often an SSD or memory upgrade. That costs far less than a new computer and can make it feel like one.',
      'upgrades'];
    var VIRUS = ['Pop-ups or acting strangely',
      'Very likely a virus, spyware or adware that has got onto the machine.',
      'We find and remove it, clear out the junk it left behind, and protect you against the next one. We can back up your files first.',
      'virus'];
    var FILES = ['I\'ve lost my files',
      'A failing drive, an accidental delete, or a machine that won\'t start with your files trapped on it.',
      'Stop using it if you can, and bring it in. We can often recover documents, photos and music, then set up a backup so it can\'t happen again.',
      'data'];
    var DATA = {
      laptop: [SLOW,
        ['It won\'t turn on', 'Often the charger, battery or power circuitry. Sometimes a failed drive or motherboard.',
         'We test it in the workshop, tell you exactly what has failed and what it will cost before doing anything.', 'repairs'],
        ['Screen is cracked or blank', 'A damaged panel, or if there\'s no visible crack, a display cable or backlight fault.',
         'We check it on an external monitor to confirm the fault, then quote you for the repair.', 'repairs'],
        VIRUS, FILES],
      desktop: [SLOW,
        ['It won\'t turn on', 'On a desktop the usual suspect is the power supply. It can also be the motherboard or memory.',
         'A quick diagnosis in the workshop, then repair or replace from the parts we keep in stock, with a 1 year warranty on new parts.', 'repairs'],
        ['Blue screens or crashes', 'Faulty memory, a failing drive, overheating or a Windows problem.',
         'A full system health check to pin down the cause. If Windows needs re-installing, we back up your files first.', 'repairs'],
        VIRUS, FILES],
      phone: [
        ['Cracked screen', 'Glass and display damage from a drop.',
         'Give us a call with the make and model and we\'ll tell you what can be done, or pop in and show us.', 'devices'],
        ['It won\'t charge', 'Commonly the cable or charger, a worn charging port, or a tired battery.',
         'Bring it in with your charger and we\'ll work out which. We keep chargers and cables in stock too.', 'devices'],
        ['Something else', 'Phones fail in all sorts of ways.',
         'Call us with the make and model and what it\'s doing, and we\'ll give you an honest answer on whether it\'s worth repairing.', 'devices']],
      console: [
        ['It won\'t power on', 'Typically a power supply or internal power fault.',
         'Bring the console and its power lead in and we\'ll take a look.', 'devices'],
        ['No picture on the TV', 'Often a damaged HDMI port or cable.',
         'Try another HDMI cable first. If that doesn\'t fix it, bring it in and we\'ll check the port.', 'devices'],
        ['Loud or overheating', 'Usually dust clogging the fan and vents.',
         'Bring it in and we\'ll take a look before it does any lasting damage.', 'devices']],
      wifi: [
        ['Wi-Fi doesn\'t reach every room', 'One router struggling with thick walls, distance or a bad position.',
         'We work out the best fix for your building: extra access points, homeplugs or a wired link, and supply the kit.', 'network'],
        ['Connection keeps dropping', 'A failing router, interference, or a fault on one device rather than the network.',
         'Network troubleshooting to find where the problem really is, so you only replace what needs replacing.', 'network'],
        ['I need a network set up', 'New home, new office, or it has simply outgrown what\'s there.',
         'Wired or wireless networks, routers, switches and shared storage for homes and small businesses.', 'network']],
      printer: [
        ['I need ink', 'Nothing wrong at all. It\'s just thirsty.',
         'We stock a large range of inks and cartridges, plus refill kits. Bring the printer model or the old cartridge and we\'ll match it.', '@shop'],
        ['It won\'t connect', 'Usually a driver or Wi-Fi setup problem rather than the printer itself.',
         'Give us a call and tell us the printer model and what you\'re printing from, and we\'ll advise.', '@contact']]
    };

    var symptomBox = $('[data-symptoms]', finder), out = $('[data-result]', finder);
    var deviceBtns = $$('[data-device]', finder);

    var showResult = function (item) {
      var link = item[3].charAt(0) === '@'
        ? '<a class="btn" href="#' + item[3].slice(1) + '" data-open="' + item[3].slice(1) + '">Open ' + (item[3] === '@shop' ? 'Shop' : 'Find Us') + '</a>'
        : '<a class="btn" href="#services" data-open="services" data-tab-target="' + item[3] + '">More detail</a>';
      out.innerHTML = '<h3>Likely cause</h3><p></p><h3>What we\'d do</h3><p></p>' +
        '<div class="btn-row"><a class="btn primary" href="' + TEL + '">Call ' + PHONE + '</a>' + link + '</div>' +
        '<p class="small">A best guess from the symptoms. We always confirm the fault and the price before starting work.</p>';
      var ps = $$('p', out);
      ps[0].textContent = item[1];
      ps[1].textContent = item[2];
      out.hidden = false;
      out.style.animation = 'none'; void out.offsetWidth; out.style.animation = '';
      if (out.scrollIntoView) out.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
    };

    deviceBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        deviceBtns.forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
        symptomBox.textContent = '';
        out.hidden = true;
        DATA[btn.getAttribute('data-device')].forEach(function (item) {
          var c = doc.createElement('button');
          c.type = 'button';
          c.className = 'chip';
          c.textContent = item[0];
          c.setAttribute('aria-pressed', 'false');
          c.addEventListener('click', function () {
            $$('.chip', symptomBox).forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
            showResult(item);
          });
          symptomBox.appendChild(c);
        });
      });
    });
  }

  // ---------- Recycle bin ----------
  var bin = $('[data-bin]'), emptyBtn = $('[data-empty-bin]');
  if (bin && emptyBtn) {
    emptyBtn.addEventListener('click', function () {
      var items = $$('li', bin);
      items.forEach(function (li, i) { setTimeout(function () { li.classList.add('gone'); }, i * 110); });
      setTimeout(function () {
        bin.innerHTML = '<li class="empty">All gone. That\'s what we do.</li>';
        emptyBtn.disabled = true;
        emptyBtn.textContent = 'Recycle Bin is empty';
      }, items.length * 110 + 320);
    });
  }

  // ---------- Terminal ----------
  var termOut = $('[data-term-out]'), termForm = $('[data-term-form]');
  if (termOut && termForm) {
    var print = function (text, cls) {
      var d = doc.createElement('div');
      if (cls) d.className = cls;
      d.textContent = text;
      termOut.appendChild(d);
      termOut.scrollTop = termOut.scrollHeight;
    };
    var APPS = ['welcome', 'finder', 'book', 'services', 'shop', 'picker', 'prices', 'jargon', 'about', 'contact', 'sysinfo', 'game', 'bin'];
    var CMDS = {
      help: function () {
        print('Commands:\n  services   what we fix\n  hours      opening hours\n  where      address\n  call       phone number\n  status     are we open?\n  open <app> ' + APPS.join(', ') + '\n  clear      clear the screen\n  exit       close the terminal');
      },
      services: function () { print('PC & laptop repairs · virus removal · upgrades\nphone & console repairs · Wi-Fi & networks\ndata recovery · collect & return (from £20)\n\nTry: open services'); },
      hours: function () { print('Mon-Fri   09:30 - 17:30\nSaturday  10:00 - 13:00\nSunday    closed'); },
      where: function () { print('The Showroom, Longforth Road\nWellington, Somerset TA21 8RQ\n(on the Shell garage forecourt)\n\nTry: open contact'); },
      call: function () { print(PHONE, 'g'); },
      status: function () { try { print(shopStatus().text, 'g'); } catch (e) { CMDS.hours(); } },
      clear: function () { termOut.textContent = ''; },
      cls: function () { termOut.textContent = ''; },
      exit: function () { closeWin('terminal'); },
      whoami: function () { print('A valued customer.'); },
      date: function () { print(new Date().toString()); },
      ver: function () { print('Micro-Check OS [Version 19.98]'); },
      dir: function () { print(' Directory of C:\\MICROCHECK\n\n' + APPS.map(function (a) { return '  ' + a.toUpperCase() + '.EXE'; }).join('\n')); },
      ls: function () { CMDS.dir(); },
      sudo: function () { print('Nice try.'); },
      format: function () { print('Please don\'t. We\'d only have to fix it.'); },
      ping: function () { print('Reply from Micro-Check: friendly, time<48hrs'); },
      hello: function () { print('Hello! Type "help" to see what I can do.'); }
    };
    print('Micro-Check OS [Version 19.98]\nType "help" and press Enter.\n');
    termForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = termForm.cmd, raw = input.value.trim();
      input.value = '';
      if (!raw) return;
      print('C:\\MICROCHECK> ' + raw, 'c');
      var parts = raw.toLowerCase().split(/\s+/);
      if (parts[0] === 'open' || parts[0] === 'start') {
        if (APPS.indexOf(parts[1]) > -1) { print('Opening ' + parts[1] + ' ...', 'g'); openWin(parts[1]); }
        else print('Usage: open <' + APPS.join('|') + '>');
      } else if (Object.prototype.hasOwnProperty.call(CMDS, parts[0])) {
        CMDS[parts[0]]();
      } else {
        print('\'' + parts[0] + '\' is not recognised. Honestly, neither are half the error messages we see. Try "help".');
      }
    });
    $('[data-term]').addEventListener('click', function () { if (!isPhone()) termForm.cmd.focus(); });
  }

  // ---------- Repair note ----------
  var noteForm = $('[data-note-form]'), ticket = $('[data-ticket]');
  if (noteForm && ticket) {
    noteForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var f = noteForm.elements, dl = $('[data-ticket-body]');
      var rows = [['Name', f.name.value], ['Device', f.device.value + (f.model.value.trim() ? ' · ' + f.model.value.trim() : '')],
        ['Problem', f.problem.value], ['Files', f.data.value], ['Bringing it in', f.day.value]];
      dl.textContent = '';
      rows.forEach(function (r) {
        var dt = doc.createElement('dt'), dd = doc.createElement('dd');
        dt.textContent = r[0]; dd.textContent = r[1].trim();
        dl.appendChild(dt); dl.appendChild(dd);
      });
      $('[data-ticket-date]').textContent = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
      noteForm.hidden = true;
      ticket.hidden = false;
    });
    $('[data-note-edit]').addEventListener('click', function () { ticket.hidden = true; noteForm.hidden = false; });
    $('[data-print]').addEventListener('click', function () { window.print(); });
  }

  // ---------- PC picker ----------
  var picker = $('[data-picker]');
  if (picker) {
    var SPEC = {
      browse: ['Any current entry-level processor', '8GB', '256GB SSD', 'Built-in graphics is all you need',
        'A refurbished machine is ideal for this and can save you a lot of money.'],
      office: ['Mid-range, such as Intel Core i5 or AMD Ryzen 5', '16GB', '512GB SSD', 'Built-in graphics is fine',
        'A comfortable keyboard and a decent screen matter more here than raw speed.'],
      photo: ['Fast multi-core, such as Intel Core i7 or AMD Ryzen 7', '16GB, or 32GB for video', '1TB SSD, plus a separate backup drive', 'A dedicated graphics card helps with video',
        'Budget for a backup drive. Your photos are worth more than the computer.'],
      gaming: ['Intel Core i5 / AMD Ryzen 5 or better', '16GB minimum, 32GB ideal', '1TB SSD', 'A dedicated graphics card. This is the part that matters most',
        'Put most of the budget into the graphics card. We can build one around the games you play.']
    };
    var TYPE = {
      laptop: 'As a laptop: check the screen size and weight suit how you\'ll carry it.',
      desktop: 'As a desktop: you get more for your money, and it\'s easy to upgrade later.',
      unsure: 'Laptop or desktop? If it never leaves the desk, a desktop gives you more for less and is easier to upgrade.'
    };
    var picks = {};
    var pickOut = $('[data-pick-result]', picker);
    $$('[data-pick]', picker).forEach(function (group) {
      $$('.chip', group).forEach(function (c) {
        c.addEventListener('click', function () {
          $$('.chip', group).forEach(function (x) { x.setAttribute('aria-pressed', String(x === c)); });
          picks[group.getAttribute('data-pick')] = c.getAttribute('data-v');
          if (!picks.use || !picks.type) return;
          var s = SPEC[picks.use];
          if (picks.use === 'gaming' && picks.type === 'laptop') s = s.slice(0, 4).concat(['Gaming laptops cost more for the same power. Worth it only if you really need to carry it.']);
          pickOut.innerHTML = '<table class="props"><tr><th>Processor</th><td></td></tr><tr><th>Memory</th><td></td></tr><tr><th>Storage</th><td></td></tr><tr><th>Graphics</th><td></td></tr></table>' +
            '<h3>Our tip</h3><p></p><p class="small"></p>' +
            '<div class="btn-row"><a class="btn primary" href="' + TEL + '">Call ' + PHONE + '</a><a class="btn" href="#shop" data-open="shop">See the shop</a><a class="btn" href="#jargon" data-open="jargon">What do these words mean?</a></div>' +
            '<p class="small">A starting point, not a quote. Tell us your budget and we\'ll match it from stock, find a refurbished one or build it.</p>';
          $$('td', pickOut).forEach(function (td, i) { td.textContent = s[i]; });
          var ps = $$('p', pickOut);
          ps[0].textContent = s[4];
          ps[1].textContent = TYPE[picks.type];
          pickOut.hidden = false;
          pickOut.style.animation = 'none'; void pickOut.offsetWidth; pickOut.style.animation = '';
          pickOut.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
        });
      });
    });
  }

  // ---------- Jargon buster ----------
  var jSearch = $('[data-jargon-search]');
  if (jSearch) {
    jSearch.addEventListener('input', function () {
      var norm = function (s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ''); };
      var q = norm(jSearch.value), shown = 0;
      $$('[data-jargon] > div').forEach(function (d) {
        var hit = !q || norm(d.textContent).indexOf(q) > -1;
        d.hidden = !hit;
        if (hit) shown++;
      });
      $('[data-jargon-none]').hidden = shown > 0;
    });
  }

  // ---------- This device ----------
  var sysTable = $('[data-sysinfo]');
  if (sysTable) {
    var ua = navigator.userAgent, uad = navigator.userAgentData;
    var addRow = function (k, v) {
      if (!v) return;
      var tr = doc.createElement('tr'), th = doc.createElement('th'), td = doc.createElement('td');
      th.textContent = k; td.textContent = v;
      tr.appendChild(th); tr.appendChild(td); sysTable.appendChild(tr);
      return td;
    };
    var advise = function (text) {
      var el = $('[data-sys-advice]');
      el.textContent = (el.textContent ? el.textContent + ' ' : '') + text;
      el.hidden = false;
    };
    var os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad|iPod/.test(ua) ? 'iOS' :
      /Mac OS X/.test(ua) ? 'macOS' : /CrOS/.test(ua) ? 'ChromeOS' : /Linux/.test(ua) ? 'Linux' : 'Unknown';
    var browser = /Edg\//.test(ua) ? 'Microsoft Edge' : /OPR\//.test(ua) ? 'Opera' : /Firefox\//.test(ua) ? 'Firefox' :
      /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Unknown';
    var touch = navigator.maxTouchPoints > 0;
    var kind = /Mobi|iPhone|Android.*Mobile/.test(ua) ? 'Phone' : (touch && Math.min(screen.width, screen.height) < 1100 && os !== 'Windows') ? 'Tablet' : 'Computer';
    addRow('Device', kind + (touch && kind === 'Computer' ? ' with a touch screen' : ''));
    var osCell = addRow('System', os);
    addRow('Browser', browser);
    addRow('Screen', screen.width + ' × ' + screen.height + ' pixels');
    if (navigator.hardwareConcurrency) addRow('Processor', navigator.hardwareConcurrency + ' threads');
    if (navigator.deviceMemory) addRow('Memory', navigator.deviceMemory >= 8 ? '8GB or more' : 'about ' + navigator.deviceMemory + 'GB');
    var conn = navigator.connection;
    addRow('Internet', navigator.onLine ? 'Connected' + (conn && conn.effectiveType ? ' (' + conn.effectiveType + ' speed class)' : '') : 'Offline');
    addRow('Language', navigator.language);
    if (navigator.getBattery) {
      navigator.getBattery().then(function (b) {
        addRow('Battery', Math.round(b.level * 100) + '%' + (b.charging ? ', charging' : ''));
      }).catch(function () {});
    }
    if (navigator.deviceMemory && navigator.deviceMemory <= 4 && kind === 'Computer') {
      advise('About ' + navigator.deviceMemory + 'GB of memory is on the tight side these days. A memory upgrade is often quick and inexpensive.');
    }
    if (os === 'Windows' && uad && uad.getHighEntropyValues) {
      uad.getHighEntropyValues(['platformVersion']).then(function (v) {
        var major = parseInt((v.platformVersion || '0').split('.')[0], 10);
        if (major >= 13) osCell.textContent = 'Windows 11';
        else if (major > 0) {
          osCell.textContent = 'Windows 10';
          advise('This looks like Windows 10. Microsoft ended support for it in October 2025, so it no longer gets security updates as standard. Ask us about your options.');
        }
      }).catch(function () {});
    }
  }

  // ---------- Virus Zapper ----------
  var game = $('[data-game]');
  if (game) {
    var grid = $('[data-grid]', game), bugSvg = $('[data-bug-src]', game).innerHTML;
    var scoreEl = $('[data-score]', game), timeEl = $('[data-time]', game), bestEl = $('[data-best]', game);
    var msg = $('[data-game-msg]', game), startGame = $('[data-game-start]', game);
    var score = 0, left = 0, spawn, clock, best = 0;
    try { best = parseInt(localStorage.getItem('mc-best') || '0', 10); } catch (e) { /* ignore */ }
    bestEl.textContent = best;
    for (var c = 0; c < 16; c++) {
      var cell = doc.createElement('button');
      cell.type = 'button';
      cell.setAttribute('aria-label', 'Zap');
      cell.innerHTML = bugSvg;
      grid.appendChild(cell);
    }
    var cells = $$('button', grid);
    grid.addEventListener('pointerdown', function (e) {
      var b = e.target.closest('button');
      if (!b || !b.classList.contains('up')) return;
      b.classList.remove('up');
      b.classList.add('zap');
      setTimeout(function () { b.classList.remove('zap'); }, 200);
      scoreEl.textContent = ++score;
    });
    var endGame = function () {
      clearInterval(spawn); clearInterval(clock);
      cells.forEach(function (b) { b.classList.remove('up'); });
      game.classList.remove('playing');
      if (score > best) { best = score; bestEl.textContent = best; try { localStorage.setItem('mc-best', String(best)); } catch (e) { /* ignore */ } }
      msg.innerHTML = 'You zapped <b>' + score + '</b>. ' + (score >= 20 ? 'We should hire you.' : score >= 10 ? 'Not bad at all.' : 'They\'re quicker than they look.') +
        ' Got a real one? <a href="#services" data-open="services" data-tab-target="virus">We remove those properly.</a>';
      startGame.hidden = false;
    };
    startGame.addEventListener('click', function () {
      score = 0; left = 20;
      scoreEl.textContent = '0'; timeEl.textContent = '20';
      msg.textContent = 'Go!';
      startGame.hidden = true;
      game.classList.add('playing');
      spawn = setInterval(function () {
        var free = cells.filter(function (b) { return !b.classList.contains('up'); });
        var b = free[Math.floor(Math.random() * free.length)];
        if (!b) return;
        b.classList.add('up');
        setTimeout(function () { b.classList.remove('up'); }, 950);
      }, 520);
      clock = setInterval(function () {
        timeEl.textContent = --left;
        if (left <= 0) endGame();
      }, 1000);
    });
  }
})();
