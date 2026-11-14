"""The connected inbox.

In the demo the inbox is the folder data/inbox/: one .eml file per message, with real
attachments. Every message is loaded when the demo resets but stays "not yet arrived"
(imported_at is NULL) until the story clock reaches its Date header. Then it is imported,
its attachments are registered as documents and the AI extraction runs.

To connect a real mailbox later, replace load_inbox() with an IMAP or Gmail API reader
that produces the same rows; nothing else has to change.
"""
import email, glob, json, os
from email import policy
from email.utils import parsedate_to_datetime

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

DOC_TYPES = [('POD_', 'delivery_receipt'), ('LotLabel_', 'lot_label_photo'),
             ('DestroyedProduct_', 'destroyed_photo'), ('DestructionForm_', 'destruction_form')]


def parse(path):
    with open(path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    body = msg.get_body(preferencelist=('plain',))
    atts = [{'filename': p.get_filename(), 'content_type': p.get_content_type(), 'size': len(p.get_payload(decode=True))}
            for p in msg.iter_attachments()]
    when = parsedate_to_datetime(msg['Date']).replace(tzinfo=None).isoformat()
    return {'message_id': msg['Message-ID'], 'event_key': msg['X-TraceReady-Event'], 'case_id': msg['X-TraceReady-Case'],
            'from_addr': str(msg['From']), 'to_addr': str(msg['To']), 'subject': str(msg['Subject']),
            'body': body.get_content().strip() if body else '', 'sent_at': when, 'attachments': atts,
            'file': os.path.relpath(path, DATA)}


def attachment(path, n):
    with open(os.path.join(DATA, path), 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    p = list(msg.iter_attachments())[n]
    return p.get_filename(), p.get_content_type(), p.get_payload(decode=True)


def load_inbox(db):
    for path in sorted(glob.glob(os.path.join(DATA, 'inbox', '*.eml'))):
        m = parse(path)
        db.execute('INSERT INTO emails (direction, message_id, event_key, case_id, from_addr, to_addr, subject, body, sent_at, file) VALUES (?,?,?,?,?,?,?,?,?,?)',
                   ('in', m['message_id'], m['event_key'], m['case_id'], m['from_addr'], m['to_addr'], m['subject'], m['body'], m['sent_at'], m['file']))


def expected(name):
    p = os.path.join(DATA, 'expected', name)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def extract(row, atts):
    """Fixture extraction: return the checked answer from data/expected/.
    An LLM extractor would read the attachments instead and return the same shape."""
    ev = row['event_key']
    if ev == 'ev2':
        return 'supplier_lot_reply', expected('supplier_lot_reply.json')
    if ev == 'ev3':
        inv = [a['filename'] for a in atts if a['filename'].startswith('POD_') and a['filename'].endswith('.pdf')]
        return 'delivery_receipt', expected('pod_%s.json' % inv[0].split('_')[1]) if inv else None
    if ev == 'ev4':
        return 'fda_request', expected('fda_request.json')
    if ev in ('ev6', 'ev7', 'ev9'):
        rk = {'ev6': 'rpl1', 'ev7': 'rpl2', 'ev9': 'rpl3'}[ev]
        return 'recall_reply', expected('recall_reply_%s.json' % rk)
    return None, None


def poll(db, until):
    """Import every message whose Date is at or before the story clock."""
    rows = db.execute("SELECT * FROM emails WHERE direction = 'in' AND imported_at IS NULL AND sent_at <= ? ORDER BY sent_at", (until,)).fetchall()
    imported = []
    for r in rows:
        r = dict(r)
        db.execute('UPDATE emails SET imported_at = ? WHERE id = ?', (until, r['id']))
        atts = parse(os.path.join(DATA, r['file']))['attachments']
        for a in atts:
            dt = next((t for pre, t in DOC_TYPES if a['filename'].startswith(pre)), 'attachment')
            db.execute('INSERT INTO documents (case_id, email_id, filename, doc_type, path, source) VALUES (?,?,?,?,?,?)',
                       (r['case_id'], r['id'], a['filename'], dt, r['file'], 'email'))
        kind, fields = extract(r, atts)
        if fields:
            db.execute('INSERT INTO extractions (email_id, source_file, kind, fields_json, method, created_at) VALUES (?,?,?,?,?,?)',
                       (r['id'], r['file'], kind, json.dumps(fields), 'fixture', until))
        r['imported_at'] = until
        r['attachments'] = atts
        imported.append(r)
    return imported
