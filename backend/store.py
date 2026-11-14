"""Database access: reset + seed, sync from the web page, and read queries."""
import base64, glob, json, os, sqlite3, threading

import fda, mailbox

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'data')
RUNTIME = os.path.join(HERE, 'runtime')
DB_PATH = os.environ.get('TRACEREADY_DB', os.path.join(RUNTIME, 'traceready.db'))  # set TRACEREADY_DB to keep the database elsewhere
LOCK = threading.Lock()


def seed(name):
    with open(os.path.join(DATA, 'seed', name), encoding='utf-8') as f:
        return json.load(f)


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def untime(v):
    """Seed files mark times as {"$t": "2026-11-12T15:05:00"}; return the plain string."""
    return v['$t'] if isinstance(v, dict) and '$t' in v else v


# ---------------------------------------------------------------- reset
def reset():
    with LOCK:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        for f in glob.glob(os.path.join(RUNTIME, 'signatures', '*.png')):
            os.remove(f)
        db = connect()
        with open(os.path.join(HERE, 'schema.sql'), encoding='utf-8') as f:
            db.executescript(f.read())
        company, recv = seed('company.json'), seed('receiving_shipment.json')
        loc = company['location']
        db.execute('INSERT INTO trading_partners (name, role, email, phone, street, city, state, zip, country) VALUES (?,?,?,?,?,?,?,?,?)',
                   (loc['name'], 'self', company['inbox'], loc['phone'], loc['street'], loc['city'], loc['state'], loc['zip'], loc['country']))
        sl = recv['loc']
        db.execute('INSERT INTO trading_partners (name, role, email, phone, street, city, state, zip, country) VALUES (?,?,?,?,?,?,?,?,?)',
                   (recv['supplier'], 'supplier', recv.get('email'), sl['phone'], sl['street'], sl['city'], sl['state'], sl['zip'], sl['country']))
        for c in seed('customers.json'):
            l = c['loc']
            db.execute('INSERT INTO trading_partners (name, role, contact, phone, street, city, state, zip, country) VALUES (?,?,?,?,?,?,?,?,?)',
                       (c['c'], 'customer', c['contact'], l['phone'], l['street'], l['city'], l['state'], l['zip'], l['country']))
        db.execute("INSERT INTO trading_partners (name, role, email) VALUES ('U.S. Food and Drug Administration', 'regulator', 'records-request@fda.example')")
        gtin = {l['p']: l['gtin'] for l in recv['lines']}
        for name, d in seed('product_descriptions.json').items():
            db.execute('INSERT INTO products VALUES (?,?,?,?,?,?)', (name, d[0], d[1], d[2], d[3], gtin.get(name)))
        for f in recv['files']:
            kind = {'inv': 'invoice', 'pk': 'packing_slip', 'bol': 'bill_of_lading', 'lbl': 'pallet_label'}[f['kind']]
            db.execute('INSERT INTO documents (case_id, filename, doc_type, path, source) VALUES (?,?,?,?,?)',
                       (recv['caseId'], f['name'], kind, 'documents/receiving/' + f['name'].rsplit('.', 1)[0] + '.pdf', 'upload'))
        mailbox.load_inbox(db)
        # history and open cases as they are before the story starts
        hist = seed('history.json')['records']
        _write_records(db, [{'id': h['id'], 'type': h['type'], 'supplier': h['supplier'], 'products': h['products'], 'lots': h['lots'],
                             'owner': h['owner'], 'signer': h['signer'], 'created': untime(h['created']), 'completed': untime(h['completed']),
                             'receiving': [r[:36] for r in h['tabs'][0]['rows']], 'shipping': []} for h in hist])
        for cid, c in seed('open_cases.json')['cases'].items():
            db.execute('INSERT INTO cases (id, kind, status, owner, created_at, updated_at) VALUES (?,?,?,?,?,?)',
                       (cid, 'receiving', 'new_update' if c.get('unread') else 'pending', c['owner'], untime(c['created']), untime(c['lastUpdate'])))
        _recompute_lots(db, [])
        db.execute("INSERT INTO demo_state VALUES ('clock', ?)", (seed('timeline.json')['events'][0]['at'][:10] + 'T08:00:00',))
        db.commit()
        db.close()


def bootstrap():
    """Everything the web page needs to start the story."""
    previews = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(DATA, 'documents', 'previews', '*.svg')))
    return {
        'company': seed('company.json'), 'receiving': seed('receiving_shipment.json'), 'customers': seed('customers.json'),
        'shipments': seed('shipments.json')['shipments'], 'history': seed('history.json')['records'],
        'openCases': seed('open_cases.json')['cases'], 'timeline': seed('timeline.json'),
        'productDescriptions': seed('product_descriptions.json'),
        'images': {k: '/files/previews/%s.svg' % k for k in previews},
    }


# ---------------------------------------------------------------- sync
def _write_records(db, records):
    for r in records:
        kind = {'recv': 'receiving', 'fda': 'fda_request', 'recall': 'recall', 'ship': 'shipping'}.get(r['type'], r['type'])
        db.execute('INSERT OR REPLACE INTO cases (id, kind, status, supplier, products, lots, owner, signer, created_at, updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (r['id'], kind, 'complete', r.get('supplier'), r.get('products'), r.get('lots'), r.get('owner'), r.get('signer'),
                    r.get('created'), r.get('completed'), r.get('completed')))
        for row in r.get('receiving') or []:
            rec = fda.row_to_record('receiving', row)
            rec['case_id'] = r['id']
            db.execute('INSERT INTO receiving_events (%s) VALUES (%s)' % (','.join(rec), ','.join('?' * len(rec))), list(rec.values()))
        for row in r.get('shipping') or []:
            rec = fda.row_to_record('shipping', row)
            rec['case_id'] = r['id']
            rec['confirm_case_id'] = r.get('shipCase')
            db.execute('INSERT INTO shipping_events (%s) VALUES (%s)' % (','.join(rec), ','.join('?' * len(rec))), list(rec.values()))


def _recompute_lots(db, recalled):
    db.execute('DELETE FROM lots')
    for r in db.execute('SELECT tlc, product_name, prev_source_name, tlc_source_name, SUM(CAST(quantity AS INTEGER)) q FROM receiving_events GROUP BY tlc').fetchall():
        shipped = db.execute('SELECT COALESCE(SUM(CAST(quantity AS INTEGER)), 0) FROM shipping_events WHERE tlc = ?', (r['tlc'],)).fetchone()[0]
        db.execute('INSERT INTO lots VALUES (?,?,?,?,?,?,?,?)', (r['tlc'], r['product_name'], r['prev_source_name'], r['tlc_source_name'],
                                                              r['q'], shipped, r['q'] - shipped, 'recalled' if r['tlc'] in recalled else 'active'))


def _save_signature(case_id, step, data_url):
    if not data_url or not data_url.startswith('data:image/png;base64,'):
        return None
    os.makedirs(os.path.join(RUNTIME, 'signatures'), exist_ok=True)
    name = '%s_%s.png' % (case_id, step)
    with open(os.path.join(RUNTIME, 'signatures', name), 'wb') as f:
        f.write(base64.b64decode(data_url.split(',', 1)[1]))
    return name


def sync(p):
    """The web page sends its full working state after every change; store it as tables."""
    with LOCK:
        db = connect()
        for t in ('cases', 'receiving_events', 'shipping_events', 'signatures', 'audit_log', 'recall_contacts'):
            db.execute('DELETE FROM ' + t)
        _write_records(db, p.get('records', []))
        for c in p.get('openCases', []):
            db.execute('INSERT OR REPLACE INTO cases (id, kind, status, title, supplier, owner, created_at, updated_at, reasons) VALUES (?,?,?,?,?,?,?,?,?)',
                       (c['id'], c['kind'], c['status'], c.get('title'), c.get('supplier'), c.get('owner'), c.get('created'), c.get('updated'), json.dumps(c.get('reasons', []))))
        for s in p.get('signatures', []):
            img = _save_signature(s['caseId'], s['step'], s.get('image'))
            db.execute('INSERT INTO signatures (case_id, step, signer, signed_at, image_file) VALUES (?,?,?,?,?)', (s['caseId'], s['step'], s['signer'], s['at'], img))
        for a in p.get('audit', []):
            db.execute('INSERT INTO audit_log (case_id, at, actor, action) VALUES (?,?,?,?)', (a['caseId'], a['at'], a['actor'], a['action']))
        inc = p.get('incident')
        if inc:
            for r in inc.get('contacts', []):
                db.execute('INSERT INTO recall_contacts (incident_id, lot, customer, contact, phone, delivered, invoice, cases_received, status, overdue, calls, reply_at, destroyed, sold_before_notice) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (inc['id'], inc['lot'], r['customer'], r.get('contact'), r.get('phone'), r.get('delivered'), r.get('invoice'), r.get('received'),
                            r.get('status'), 1 if r.get('overdue') else 0, json.dumps(r.get('calls', [])), r.get('replyAt'), r.get('destroyed'), r.get('sold')))
        # the receiving documents were read once the case was grouped
        if p.get('receivingRead') and not db.execute("SELECT 1 FROM extractions WHERE kind = 'receiving_documents'").fetchone():
            exp = mailbox.expected('receiving_%s.json' % seed('receiving_shipment.json')['inv'])
            db.execute('INSERT INTO extractions (source_file, kind, fields_json, method, created_at) VALUES (?,?,?,?,?)',
                       ('documents/receiving/', 'receiving_documents', json.dumps(exp), 'fixture', p.get('clock')))
        _recompute_lots(db, p.get('recalledLots', []))
        if p.get('clock'):
            db.execute("INSERT OR REPLACE INTO demo_state VALUES ('clock', ?)", (p['clock'],))
        db.commit()
        db.close()


def poll_inbox(until):
    with LOCK:
        db = connect()
        out = mailbox.poll(db, until)
        db.execute("INSERT OR REPLACE INTO demo_state VALUES ('clock', ?)", (until,))
        db.commit()
        db.close()
    return out


# ---------------------------------------------------------------- reads
def rows(sql, args=()):
    db = connect()
    try:
        return [dict(r) for r in db.execute(sql, args)]
    finally:
        db.close()


def trace(tlc):
    lot = rows('SELECT * FROM lots WHERE tlc = ?', (tlc,))
    came = rows('SELECT case_id, receive_date, quantity, prev_source_name, tlc_source_name, ref_doc_type, ref_doc_number FROM receiving_events WHERE tlc = ?', (tlc,))
    went = rows('SELECT case_id, confirm_case_id, ship_date, quantity, recipient_name, recipient_city, ref_doc_number FROM shipping_events WHERE tlc = ?', (tlc,))
    return {'lot': lot[0] if lot else None, 'cameFrom': came, 'wentTo': went}
