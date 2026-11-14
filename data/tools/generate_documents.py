"""Generate the demo's source documents from the seed data.

Writes:
  documents/receiving/  invoice, packing slip, bill of lading, pallet label (PDF)
  documents/shipping/   signed delivery receipts (PDF)
  inbox/                every email that arrives during the story (.eml, with attachments)
  expected/             the correct extraction result for each document (JSON)

Run from the project root:  python3 data/tools/generate_documents.py
Needs reportlab only for the PDFs (pip install reportlab). The generated files are
committed to the repo, so the app itself never needs reportlab.
"""
import json, os, mimetypes
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from datetime import datetime, timezone, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

DATA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(DATA, 'seed')
PST = timezone(timedelta(hours=-8))


def load(name):
    with open(os.path.join(SEED, name), encoding='utf-8') as f:
        return json.load(f)


def out(*parts):
    p = os.path.join(DATA, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def ts(v):
    return v['$t'] if isinstance(v, dict) else v


company = load('company.json')
recv = load('receiving_shipment.json')
docs = load('receiving_documents.json')['documents']
customers = load('customers.json')
shipments = load('shipments.json')['shipments']
timeline = {e['key']: e['at'] for e in load('timeline.json')['events']}
text = load('email_text.json')
LOT = load('timeline.json')['recallLot']
cust_by_name = {c['c']: c for c in customers}


# ---------- PDFs ----------
def doc_pdf(path, d, smudge=False):
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    c.setFont('Helvetica-Bold', 20); c.drawString(54, h - 72, d['title'])
    c.setFont('Helvetica', 12); c.drawRightString(w - 54, h - 72, d.get('no', ''))
    y = h - 110
    for m in d['meta']:
        c.setFont('Helvetica-Bold', 10); c.drawString(54, y, m['l'])
        c.setFont('Helvetica', 10); c.drawString(160, y, m['v']); y -= 18
    y -= 14
    cols = [54, 250, 400, 480]
    c.setFont('Helvetica-Bold', 10)
    for i, hd in enumerate(d['head']):
        c.drawString(cols[i], y, hd)
    c.line(54, y - 6, w - 54, y - 6); y -= 24
    for r in d['rows']:
        for i, v in enumerate(r['c'][:4]):
            if smudge and r.get('smudge') and i == 2:
                c.setFont('Courier-Bold', 11); c.setFillGray(0.55); c.drawString(cols[i], y, v); c.setFillGray(0)
            else:
                c.setFont('Helvetica', 10); c.drawString(cols[i], y, str(v))
        y -= 20
    if d.get('foot'):
        c.setFont('Helvetica-Oblique', 9); c.drawString(54, y - 20, d['foot'])
    c.showPage(); c.save()


def pod_pdf(path, s):
    cu = cust_by_name[s['c']]
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    c.setFont('Helvetica-Bold', 18); c.drawString(54, h - 72, 'DELIVERY RECEIPT · ' + s['inv'])
    c.setFont('Helvetica', 10)
    c.drawString(54, h - 92, 'Green Valley Produce, 1200 Harbor Rd, Oakland, CA 94607  →  ' + cu['c'] + ', ' + cu['loc']['street'] + ', ' + cu['loc']['city'])
    c.drawString(54, h - 108, 'Delivery date: ' + s['d'])
    y = h - 150
    c.setFont('Helvetica-Bold', 10)
    for x, t in ((54, 'Product'), (250, 'Lot (TLC)'), (420, 'Qty')):
        c.drawString(x, y, t)
    c.line(54, y - 6, w - 54, y - 6); y -= 24
    for p, lot, q in s['lines']:
        c.setFont('Helvetica', 10); c.drawString(54, y, p)
        c.setFont('Courier', 10); c.drawString(250, y, lot)
        c.setFont('Helvetica', 10); c.drawString(420, y, '%d CS' % q); y -= 20
    c.setFont('Helvetica', 10); c.drawString(54, y - 40, 'Received in good condition by')
    c.setFont('Helvetica-Oblique', 18); c.setFillColorRGB(0.1, 0.23, 0.54); c.drawString(240, y - 42, cu['contact']); c.setFillGray(0)
    c.line(235, y - 48, w - 54, y - 48)
    c.showPage(); c.save()


receiving_files = {}
for f in recv['files']:
    kind = f['kind']
    name = f['name'].rsplit('.', 1)[0] + '.pdf'
    p = out('documents', 'receiving', name)
    doc_pdf(p, docs[kind], smudge=(kind == 'lbl'))
    receiving_files[kind] = name

pod_files = {}
for s in shipments:
    p = out('documents', 'shipping', s['name'])
    pod_pdf(p, s)
    pod_files[s['inv']] = p


# ---------- emails ----------
def mail(fname, frm, to, when, subject, body, attachments=(), event=None, reply_to_case=None):
    m = EmailMessage()
    m['From'] = frm
    m['To'] = to
    m['Date'] = format_datetime(datetime.fromisoformat(when).replace(tzinfo=PST))
    m['Subject'] = subject
    m['Message-ID'] = make_msgid(domain='traceready.example')
    if event:
        m['X-TraceReady-Event'] = event
    if reply_to_case:
        m['X-TraceReady-Case'] = reply_to_case
    m.set_content(body)
    for path, name in attachments:
        ctype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        main, sub = ctype.split('/')
        with open(path, 'rb') as fh:
            m.add_attachment(fh.read(), maintype=main, subtype=sub, filename=name)
    with open(out('inbox', fname), 'wb') as fh:
        fh.write(bytes(m))


INBOX = company['inbox']
SUP = 'Rio Claro Growers <orders@rioclaro-growers.example>'
prev = lambda n: os.path.join(DATA, 'documents', 'previews', n)
slicer = [l for l in recv['lines'] if not l['lot']][0]

mail('01_2026-11-11_rioclaro_lot_pending.eml', SUP, INBOX, timeline['ev1'],
     'RE: Lot code needed – Slicer cucumbers (PO-4486)',
     text['mNoLot'].replace('{product}', slicer['p']), event='ev1', reply_to_case=recv['caseId'])
mail('02_2026-11-12_rioclaro_lot_code.eml', SUP, INBOX, timeline['ev2'],
     'RE: Lot code needed – Slicer cucumbers (PO-4486)',
     text['mLot'].replace('{product}', slicer['p']).replace('{lot}', slicer['realLot']),
     [(prev('label_' + slicer['realLot'] + '.svg'), 'LotLabel_' + slicer['realLot'] + '.svg')], event='ev2', reply_to_case=recv['caseId'])
for i, s in enumerate(shipments):
    cu = cust_by_name[s['c']]
    body = text['podMail'].replace('{inv}', s['inv']).replace('{who}', cu['contact']).replace('{c}', cu['c'])
    mail('%02d_%s_%s_signed_receipt.eml' % (3 + i, ts(s['ts'])[:10], cu['c'].split(' ')[0].lower()),
         '%s, %s <receiving@%s.example>' % (cu['contact'], cu['c'], cu['c'].split(' ')[0].lower()), INBOX, ts(s['ts']),
         'Signed delivery receipt – invoice ' + s['inv'], body,
         [(pod_files[s['inv']], s['name']), (prev('pod_' + s['inv'] + '.svg'), s['name'].replace('.pdf', '_preview.svg'))], event='ev3')
mail('06_2026-12-01_fda_records_request.eml', 'FDA Office of Coordinated Outbreak Response <records-request@fda.example>', INBOX, timeline['ev4'],
     'Records request under 21 CFR 1.1455 – fresh cucumbers', text['fdaMail'], event='ev4')
mail('07_2026-12-03_rioclaro_recall_notice.eml', 'L. Moreno, Rio Claro Growers <foodsafety@rioclaro-growers.example>', INBOX, timeline['ev5'],
     'VOLUNTARY RECALL – Slicer cucumbers lot ' + LOT, text['recallMail'], event='ev5')
for n, (cu, ev) in enumerate(zip(customers, ['ev6', 'ev7', 'ev9'])):
    short = cu['c'].split(' ')[0]
    mail('%02d_%s_%s_recall_reply.eml' % (8 + n, timeline[ev][:10], short.lower()),
         '%s, %s <receiving@%s.example>' % (cu['contact'], cu['c'], short.lower()), INBOX, timeline[ev],
         'RE: URGENT recall – Slicer cucumbers lot ' + LOT, text[cu['rk']],
         [(prev('photo_' + cu['rk'] + '.svg'), 'DestroyedProduct_%s.svg' % short), (prev('form_' + cu['rk'] + '.svg'), 'DestructionForm_%s_signed.svg' % short)], event=ev)
mail('11_2026-12-05_rioclaro_ack.eml', 'L. Moreno, Rio Claro Growers <foodsafety@rioclaro-growers.example>', INBOX, timeline['ev10'],
     'RE: Recall report – lot ' + LOT, text['ackMail'], event='ev10')


# ---------- expected extraction results ----------
def W(name, o):
    with open(out('expected', name), 'w', encoding='utf-8') as fh:
        json.dump(o, fh, ensure_ascii=False, indent=2)


W('receiving_' + recv['inv'] + '.json', {
    'caseId': recv['caseId'], 'documents': receiving_files,
    'fields': {'supplier': recv['supplier'], 'supplierLocation': recv['loc'], 'po': recv['po'], 'invoice': recv['inv'], 'bol': recv['bol'],
               'shipDate': recv['ship'], 'receiveDate': recv['recv'], 'tlcSource': recv['packer']},
    'lines': [{'product': l['p'], 'gtin': l['gtin'], 'packDate': l['pack'], 'unit': l['unit'],
               'lotOnDocuments': l['lot'] or None, 'qtyInvoice': l['qi'], 'qtyPackingSlip': l['qp']} for l in recv['lines']],
    'problems': [
        {'type': 'missing_lot', 'product': slicer['p'], 'why': 'Lot code is smudged on the pallet label and missing on the invoice.'},
        {'type': 'quantity_conflict', 'product': slicer['p'], 'invoice': slicer['qi'], 'packingSlip': slicer['qp'], 'billOfLading': slicer['qp']}]})
W('supplier_lot_reply.json', {'event': 'ev2', 'product': slicer['p'], 'lot': slicer['realLot'], 'evidence': 'LotLabel_' + slicer['realLot'] + '.svg'})
for s in shipments:
    cu = cust_by_name[s['c']]
    W('pod_' + s['inv'] + '.json', {'event': 'ev3', 'customer': cu['c'], 'customerLocation': cu['loc'], 'invoice': s['inv'], 'deliveryDate': s['d'],
                                    'receivedBy': cu['contact'], 'lines': [{'product': p, 'lot': lot, 'qty': q, 'unit': 'CS'} for p, lot, q in s['lines']]})
for cu in customers:
    W('recall_reply_' + cu['rk'] + '.json', {'customer': cu['c'], 'lot': LOT, 'casesReceived': cu['q'], 'destroyed': cu['destroyed'],
                                             'soldBeforeNotice': cu['sold'], 'method': 'Compactor / landfill', 'signedBy': cu['contact']})
W('fda_request.json', {'event': 'ev4', 'commodity': 'Fresh cucumbers', 'supplier': recv['supplier'], 'from': '2026-11-01', 'to': '2026-11-15', 'deadlineHours': 24})
print('documents, inbox and expected written')
