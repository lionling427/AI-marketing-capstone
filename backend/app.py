"""TraceReady demo server.

    python3 backend/app.py            then open http://localhost:8000

Uses only the Python standard library (3.8+): nothing to install.
Serves the web page from frontend/, the documents from data/, and the JSON API under /api/.
"""
import json, mimetypes, os, sys, threading, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks, fda, mailbox, store  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, 'frontend')
DOCS = os.path.join(ROOT, 'data', 'documents')
PORT = int(os.environ.get('PORT', '8000'))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=FRONTEND, **kw)

    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else '') and os.environ.get('QUIET') != '1':
            sys.stderr.write('  %s\n' % (args[0],))

    # ---------- helpers
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, indent=1).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, data, ctype, filename=None):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def end_headers(self):
        if self.path.endswith(('.html', '.js', '.css', '/')):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    # ---------- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path
        if p.startswith('/files/'):
            return self.serve_file(os.path.join(DOCS, unquote(p[len('/files/'):])))
        if not p.startswith('/api/'):
            return super().do_GET()
        try:
            return self.api_get(p[len('/api'):], q)
        except Exception as e:  # keep the demo running and say what went wrong
            return self.send_json({'error': str(e)}, 500)

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            if p == '/api/demo/reset':
                store.reset()
                return self.send_json({'ok': True})
            if p == '/api/sync':
                store.sync(self.body())
                return self.send_json({'ok': True})
            if p == '/api/inbox/poll':
                return self.send_json({'imported': store.poll_inbox(self.body()['until'])})
        except Exception as e:
            return self.send_json({'error': str(e)}, 500)
        self.send_json({'error': 'not found'}, 404)

    def api_get(self, p, q):
        if p == '/health':
            return self.send_json({'ok': True, 'clock': store.rows("SELECT value FROM demo_state WHERE key = 'clock'")[0]['value']})
        if p == '/bootstrap':
            return self.send_json(store.bootstrap())
        if p == '/cases':
            sql, args = 'SELECT * FROM cases', ()
            if q.get('status'):
                sql, args = sql + ' WHERE status = ?', (q['status'],)
            return self.send_json(store.rows(sql + ' ORDER BY updated_at DESC', args))
        if p == '/history':
            out = store.rows("SELECT * FROM cases WHERE status = 'complete' ORDER BY created_at DESC")
            if q.get('date'):
                out = [c for c in out if (c['created_at'] or '').startswith(q['date']) or (c['completed_at'] or '').startswith(q['date'])]
            if q.get('lot'):
                out = [c for c in out if q['lot'].upper() in (c['lots'] or '').upper()]
            return self.send_json(out)
        if p.startswith('/cases/'):
            cid = p.split('/')[2]
            c = store.rows('SELECT * FROM cases WHERE id = ?', (cid,))
            return self.send_json({'case': c[0] if c else None,
                                   'receiving': store.rows('SELECT * FROM receiving_events WHERE case_id = ?', (cid,)),
                                   'shipping': store.rows('SELECT * FROM shipping_events WHERE case_id = ?', (cid,)),
                                   'signatures': store.rows('SELECT * FROM signatures WHERE case_id = ?', (cid,)),
                                   'audit': store.rows('SELECT * FROM audit_log WHERE case_id = ? ORDER BY at', (cid,)),
                                   'documents': store.rows('SELECT * FROM documents WHERE case_id = ?', (cid,))})
        if p == '/lots':
            return self.send_json(store.rows('SELECT * FROM lots ORDER BY tlc'))
        if p.startswith('/trace/'):
            return self.send_json(store.trace(unquote(p.split('/')[2])))
        if p == '/inbox':
            sql = "SELECT id, event_key, case_id, from_addr, subject, body, sent_at, imported_at, file FROM emails WHERE direction = 'in'"
            if q.get('all') != '1':
                sql += ' AND imported_at IS NOT NULL'
            return self.send_json(store.rows(sql + ' ORDER BY sent_at'))
        if p.startswith('/emails/') and '/attachments/' in p:
            parts = p.split('/')
            e = store.rows('SELECT file FROM emails WHERE id = ?', (int(parts[2]),))[0]
            name, ctype, data = mailbox.attachment(e['file'], int(parts[4]))
            return self.send_bytes(data, ctype, name)
        if p == '/documents':
            return self.send_json(store.rows('SELECT * FROM documents ORDER BY id'))
        if p == '/extractions':
            out = store.rows('SELECT * FROM extractions ORDER BY id')
            for r in out:
                r['fields'] = json.loads(r.pop('fields_json'))
            return self.send_json(out)
        if p == '/signatures':
            return self.send_json(store.rows('SELECT * FROM signatures ORDER BY signed_at'))
        if p.startswith('/signatures/'):
            return self.serve_file(os.path.join(store.RUNTIME, 'signatures', os.path.basename(p)))
        if p == '/audit':
            sql, args = 'SELECT * FROM audit_log', ()
            if q.get('case'):
                sql, args = sql + ' WHERE case_id = ?', (q['case'],)
            return self.send_json(store.rows(sql + ' ORDER BY at', args))
        if p == '/recall':
            return self.send_json(store.rows('SELECT * FROM recall_contacts ORDER BY id'))
        if p == '/compliance':
            db = store.connect()
            try:
                return self.send_json(fda.compliance(db))
            finally:
                db.close()
        if p == '/validation':
            return self.send_json(self.validation())
        if p in ('/export/fda.csv', '/export/fda'):
            cte = 'shipping' if q.get('cte') == 'shipping' else 'receiving'
            db = store.connect()
            try:
                data = fda.to_csv(cte, fda.query_events(db, cte, q.get('lot'), q.get('from'), q.get('to'), q.get('case')))
            finally:
                db.close()
            return self.send_bytes(data.encode('utf-8'), 'text/csv; charset=utf-8', 'fda_%s%s.csv' % (cte, ('_' + q['lot']) if q.get('lot') else ''))
        self.send_json({'error': 'not found'}, 404)

    def validation(self):
        """Re-run every rule on what the server has: documents read, receipts imported, recall forms, saved records."""
        ex = {}
        for r in store.rows('SELECT kind, fields_json FROM extractions'):
            ex.setdefault(r['kind'], []).append(json.loads(r['fields_json']))
        out = {}
        for rec in ex.get('receiving_documents', []):
            out['receiving'] = checks.receiving_problems([{'product': l['product'], 'lot': l['lotOnDocuments'], 'qtyInvoice': l['qtyInvoice'],
                                                           'qtyPackingSlip': l['qtyPackingSlip']} for l in rec['lines']])
        received = {l['tlc']: l['received_qty'] for l in store.rows('SELECT tlc, received_qty FROM lots')}
        out['shipping'] = checks.shipment_problems(received, [{'invoice': r['invoice'], 'lines': r['lines']} for r in ex.get('delivery_receipt', [])])
        out['recall'] = checks.recall_problems([{'customer': r['customer'], 'received': r['casesReceived'], 'destroyed': r['destroyed'], 'sold': r['soldBeforeNotice']}
                                                for r in ex.get('recall_reply', [])])
        db = store.connect()
        try:
            out['kde'] = fda.compliance(db)
        finally:
            db.close()
        return out

    def serve_file(self, path):
        path = os.path.realpath(path)
        allowed = (os.path.realpath(DOCS), os.path.realpath(store.RUNTIME))
        if not path.startswith(allowed) or not os.path.isfile(path):
            return self.send_json({'error': 'not found'}, 404)
        with open(path, 'rb') as f:
            self.send_bytes(f.read(), mimetypes.guess_type(path)[0] or 'application/octet-stream')


def main():
    store.reset()
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    url = 'http://localhost:%d' % PORT
    print('TraceReady is running at %s  (press Ctrl+C to stop)' % url)
    print('API index: %s/api/health, /api/cases, /api/history, /api/inbox, /api/export/fda.csv?cte=shipping' % url)
    if os.environ.get('NO_BROWSER') != '1':
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
