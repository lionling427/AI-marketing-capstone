"""FSMA 204 helpers: the FDA template columns, CSV export and a completeness check."""
import csv, io, json, os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
LOC = ['name', 'phone', 'street', 'city', 'state', 'zip', 'country']
PRODUCT = ['product_name', 'brand_name', 'commodity', 'variety', 'packaging_size', 'packaging_style']
TAIL = ['tlc_source_reference', 'ref_doc_type', 'ref_doc_number', 'ref_doc_type2', 'ref_doc_number2']

# Database column for each FDA template column, in template order
RECEIVING_COLS = (['tlc', 'quantity', 'unit_of_measure'] + PRODUCT + ['prev_source_' + x for x in LOC]
                  + ['received_at_' + x for x in LOC] + ['receive_date'] + ['tlc_source_' + x for x in LOC] + TAIL)
SHIPPING_COLS = (['tlc', 'quantity', 'unit_of_measure'] + PRODUCT + ['recipient_' + x for x in LOC]
                 + ['shipped_from_' + x for x in LOC] + ['ship_date'] + ['tlc_source_' + x for x in LOC] + TAIL)

# Key Data Elements the rule requires for each event (the rest are "if applicable")
REQUIRED = {
    'receiving': ['tlc', 'quantity', 'unit_of_measure', 'product_name', 'prev_source_name', 'received_at_name', 'receive_date', 'tlc_source_name', 'ref_doc_type', 'ref_doc_number'],
    'shipping': ['tlc', 'quantity', 'unit_of_measure', 'product_name', 'recipient_name', 'shipped_from_name', 'ship_date', 'tlc_source_name', 'ref_doc_type', 'ref_doc_number'],
}


def headers():
    with open(os.path.join(DATA, 'seed', 'fda_columns.json'), encoding='utf-8') as f:
        h = json.load(f)
    assert len(h['receiving']) == len(RECEIVING_COLS) and len(h['shipping']) == len(SHIPPING_COLS)
    return h


def cols(cte):
    return RECEIVING_COLS if cte == 'receiving' else SHIPPING_COLS


def row_to_record(cte, row):
    """A row in template order (as the UI shows it) -> {db column: value}."""
    return {c: ('' if v is None else str(v)) for c, v in zip(cols(cte), row)}


def mdy_to_iso(s):
    try:
        m, d, y = s.split('/')
        return '%s-%s-%s' % (y, m.zfill(2), d.zfill(2))
    except ValueError:
        return ''


def query_events(db, cte, lot=None, date_from=None, date_to=None, case_id=None):
    table = 'receiving_events' if cte == 'receiving' else 'shipping_events'
    date_col = 'receive_date' if cte == 'receiving' else 'ship_date'
    rows = [dict(r) for r in db.execute('SELECT * FROM %s ORDER BY id' % table)]
    out = []
    for r in rows:
        if lot and lot.upper() not in (r['tlc'] or '').upper():
            continue
        if case_id and r['case_id'] != case_id:
            continue
        d = mdy_to_iso(r[date_col] or '')
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(r)
    return out


def to_csv(cte, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers()[cte])
    for r in rows:
        w.writerow([r.get(c, '') for c in cols(cte)])
    return buf.getvalue()


def compliance(db):
    """Which saved events are missing a required Key Data Element."""
    report = []
    for cte in ('receiving', 'shipping'):
        for r in query_events(db, cte):
            missing = [c for c in REQUIRED[cte] if not (r.get(c) or '').strip()]
            if missing:
                report.append({'event': cte, 'case_id': r['case_id'], 'tlc': r['tlc'], 'missing': missing})
    return report
