/* TraceReady – connection between the web page and the backend.
 *
 * 1. On load: reset the demo on the server, load the story data from data/ (GET /api/bootstrap),
 *    put it into the page, then draw the first screen.
 * 2. Each time the story clock moves: import the emails that have "arrived" (POST /api/inbox/poll).
 * 3. After every change on screen: send the working state to the server (POST /api/sync),
 *    which stores cases, FDA receiving/shipping events, signatures, audit trail and recall contacts.
 *
 * If the page is opened without the server (double-clicking index.html), it still runs the
 * whole story with the copy of the data built into app.js, and nothing is saved.
 */
(function () {
  var TR = window.TR = { online: false, ready: false, inbox: [], lastSync: '' };

  function lt(ms) {
    var d = new Date(ms);
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }
  function fromIso(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(s);
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)).getTime();
  }
  // seed files write times as {"$t": "2026-11-12T15:05:00"} (local time) -> milliseconds
  function dec(v) {
    if (Array.isArray(v)) return v.map(dec);
    if (v && typeof v === 'object') {
      if (Object.keys(v).length === 1 && typeof v.$t === 'string') return fromIso(v.$t);
      var o = {}; for (var k in v) o[k] = dec(v[k]); return o;
    }
    return v;
  }
  function api(method, path, body) {
    return fetch('/api' + path, { method: method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); });
  }

  // ---------- 1. load the story data from the backend ----------
  function apply(b) {
    var rcv = b.receiving;
    Object.keys(rcv).forEach(function (k) {
      if (k === 'caseId' || k === 'note') return;
      if (k === 'lines') rcv.lines.forEach(function (l, i) { if (SC.s2.lines[i]) Object.assign(SC.s2.lines[i], l); else SC.s2.lines.push(l); });
      else SC.s2[k] = rcv[k];
    });
    Object.assign(OURLOC, b.company.location);
    Object.assign(DESC, b.productDescriptions);
    b.customers.forEach(function (c, i) { if (CUST[i]) Object.assign(CUST[i], c); });
    b.shipments.forEach(function (s, i) {
      var o = OUT[i]; if (!o) return;
      var x = dec(s); var name = x.c; delete x.c; Object.assign(o, x);
      o.c = CUST.filter(function (cu) { return cu.c === name; })[0] || o.c;
    });
    LOT = b.timeline.recallLot;
    b.timeline.events.forEach(function (e) { if (EVENTS[e.index]) EVENTS[e.index].ts = fromIso(e.at); });
    S.hist = dec(b.history);
    Object.keys(b.openCases).forEach(function (id) { S.cases[id] = dec(b.openCases[id]); });
    deriveChecks();  // problems are found from the document fields
    // document pictures come from data/documents/previews/ instead of being drawn in the page
    var img = b.images || {};
    var _label = labelImg, _photo = photoImg, _form = formImg, _pod = podImg;
    labelImg = function (sc, ln) { return img['label_' + (ln.realLot || ln.lot)] || _label(sc, ln); };
    photoImg = function (cu) { return img['photo_' + cu.rk] || _photo(cu); };
    formImg = function (cu) { return img['form_' + cu.rk] || _form(cu); };
    podImg = function (o) { return img['pod_' + o.inv] || _pod(o); };
  }

  // ---------- 2. emails arrive when the story clock reaches them ----------
  var _playNext = playNext;
  playNext = function () {
    if (!TR.ready) return;
    _playNext();
    if (TR.online && S.clock) api('POST', '/inbox/poll', { until: lt(S.clock) }).then(function (r) { TR.inbox = TR.inbox.concat(r.imported); }).catch(function () {});
  };

  // ---------- 3. save the working state ----------
  var EN = {}; for (var k in T) EN[k] = T[k][0];
  var TIPEN = {}; for (var j in TIP) TIPEN[j] = TIP[j][0];
  function tx(k, o) { return T[k] ? fmt(T[k][0], o || {}) : k; }
  function stat(st) { return st === 'update' ? 'new_update' : (st === 'done' ? 'complete' : 'pending'); }

  function snapshot() {
    var p = { clock: S.clock ? lt(S.clock) : null, records: [], openCases: [], signatures: [], audit: [], incident: null, recalledLots: [], receivingRead: false };
    S.hist.forEach(function (h) {
      var r = { id: h.id, type: h.type, supplier: h.supplier, products: h.products, lots: h.lots, owner: h.owner, signer: h.signer,
        created: h.created ? lt(h.created) : null, completed: h.completed ? lt(h.completed) : null, receiving: [], shipping: [] };
      if (h.type === 'recv') {
        var tabs = tabsOf(h);
        tabs.forEach(function (tb) {
          if (tb.n === 'tabRecv') r.receiving = tb.rows.map(function (x) { return x.slice(0, RECV_H.length); });
          if (tb.n === 'tabShip') r.shipping = tb.rows;
        });
        if (h.ship) { r.shipCase = h.ship.id; r.signer = h.signer; }
      }
      p.records.push(r);
    });
    Object.keys(S.cases).forEach(function (id) {
      var c = S.cases[id];
      if (c.scen === 's2' && c.grouped) p.receivingRead = true;
      (c.audit || []).forEach(function (a) { p.audit.push({ caseId: c.id, at: lt(a.ts), actor: a.who, action: auditText(a, EN) }); });
      if (c.signed) p.signatures.push({ caseId: c.id, step: 'receiving', signer: c.signed.name, at: lt(c.signed.ts), image: c.signed.img });
      if (c.grouped && !c.signed) p.openCases.push({ id: c.id, kind: 'receiving', status: stat(statusOf(c)), owner: c.owner, supplier: SC[c.scen] ? SC[c.scen].supplier : '',
        created: lt(c.created), updated: lt(c.lastUpdate || c.created), reasons: (function () { try { return reasonOf(c, EN); } catch (e) { return []; } })() });
    });
    try {
      var extra = []; incRow(extra, EN, TIPEN);
      extra.forEach(function (r) {
        p.openCases.push({ id: r.id, kind: r.id.indexOf('SH-') === 0 ? 'shipping' : 'incident', status: stat(r.st), owner: r.owner, title: r.sum,
          created: lt(r.created), updated: lt(r.last || r.created), reasons: r.why || [] });
      });
    } catch (e) { /* no open shipping case or incident */ }
    var sc = S.shipCase;
    if (sc) {
      (sc.log || []).forEach(function (a) { p.audit.push({ caseId: sc.id, at: lt(a.ts), actor: a.who, action: tx(a.k, a.o) }); });
      if (sc.signed) p.signatures.push({ caseId: sc.id, step: 'shipping', signer: sc.signed.name, at: lt(sc.signed.ts), image: sc.signed.img });
    }
    var I = S.inc;
    if (I) {
      (I.log || []).forEach(function (a) { p.audit.push({ caseId: I.id, at: lt(a.ts), actor: a.who, action: tx(a.k, a.o) }); });
      if (I.signed) p.signatures.push({ caseId: I.id, step: 'incident', signer: I.signed.name, at: lt(I.signed.ts), image: I.signed.img });
      var R = I.recall;
      p.incident = { id: I.id, lot: I.lot, contacts: [] };
      if (R) {
        if (R.flagged) p.recalledLots.push(I.lot);
        CUST.forEach(function (cu) {
          var r = R.rows[cu.c] || {};
          p.incident.contacts.push({ customer: cu.c, contact: cu.contact, phone: cu.loc.phone, delivered: cu.d, invoice: cu.inv, received: cu.q,
            status: r.st, overdue: !!r.overdue, calls: (r.calls || []).map(function (x) { return typeof x === 'string' ? (EN[x] || x) : (EN[x.o] || x.o || x); }),
            replyAt: r.replyTs ? lt(r.replyTs) : null, destroyed: r.st === 'confirmed' ? cu.destroyed : null, sold: r.st === 'confirmed' ? cu.sold : null });
        });
      }
    }
    return p;
  }

  var timer = null;
  function scheduleSync() {
    if (!TR.online) return;
    clearTimeout(timer);
    timer = setTimeout(function () {
      var p; try { p = snapshot(); } catch (e) { console.warn('TraceReady sync skipped', e); return; }
      var s = JSON.stringify(p); if (s === TR.lastSync) return;
      TR.lastSync = s;
      fetch('/api/sync', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: s }).catch(function () {});
    }, 700);
  }
  // required disclosure: what is synthetic or simulated in this prototype
  var SYNTH = {
    en: 'Prototype · Synthetic data (fictional companies, lots and people) · Simulated inbox and story clock · AI extraction simulated with checked answers · Not connected to real email, ERP or FDA systems',
    zh: '原型 · 合成資料（公司、批號與人物皆為虛構）· 模擬信箱與故事時鐘 · AI 讀取以預先核對的答案模擬 · 未連接真實 email、ERP 或 FDA 系統',
    es: 'Prototipo · Datos sintéticos (empresas, lotes y personas ficticias) · Buzón y reloj simulados · Extracción de IA simulada con respuestas verificadas · Sin conexión a correo, ERP ni sistemas de la FDA reales'
  };
  function footer() { var f = document.getElementById('synth'); if (f) f.textContent = SYNTH[S.lang] || SYNTH.en; }
  var _render0 = render0;
  render0 = function () { _render0(); footer(); scheduleSync(); };

  // ---------- start ----------
  api('POST', '/demo/reset')
    .then(function () { return api('GET', '/bootstrap'); })
    .then(function (b) { apply(b); TR.online = true; })
    .catch(function (e) { console.info('TraceReady: running without the server (' + e.message + ')'); })
    .then(function () { TR.ready = true; render0(); });
})();
