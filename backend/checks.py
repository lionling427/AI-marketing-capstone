"""Validation rules. Pure functions so they can be tested on their own (evidence/tests).

The web page applies the same rules on screen (frontend/js/app.js, "v15" block) and the
server re-checks saved data through GET /api/validation.
Every rule answers: what is wrong, and what must a person do before the record is trusted.
"""
import re

LOT_DATE = re.compile(r'-(\d{4})-\d{2}$')


def lot_unreadable(lot):
    return not lot or '?' in lot


def receiving_problems(lines):
    """lines: [{product, lot, qtyInvoice, qtyPackingSlip, packDate}] read from the documents."""
    out = []
    for ln in lines:
        if lot_unreadable(ln.get('lot')):
            out.append({'rule': 'missing_lot', 'product': ln['product'], 'action': 'Ask the supplier for the lot code; the record cannot be signed until it is applied.'})
        if ln.get('qtyInvoice') != ln.get('qtyPackingSlip'):
            out.append({'rule': 'quantity_conflict', 'product': ln['product'], 'invoice': ln.get('qtyInvoice'), 'packingSlip': ln.get('qtyPackingSlip'),
                        'action': 'A person chooses the quantity and gives a reason.'})
    return out


def supplier_lot_problem(new_lot, product, pack_date, other_lots):
    """A lot code sent later by the supplier must be new in this delivery and carry the pack date (MMDD)."""
    if lot_unreadable(new_lot):
        return 'unreadable'
    if new_lot in other_lots:
        return 'duplicate_lot'
    m = LOT_DATE.search(new_lot)
    mmdd = (pack_date or '')[5:].replace('-', '')
    if m and mmdd and m.group(1) != mmdd:
        return 'pack_date_mismatch'
    return None


def shipment_problems(received, receipts):
    """received: {lot: cases}; receipts: [{invoice, customer, lines: [{lot, qty}]}]."""
    out, sums = [], {}
    for r in receipts:
        for ln in r['lines']:
            if ln['lot'] not in received:
                out.append({'rule': 'no_receiving_record', 'lot': ln['lot'], 'invoice': r['invoice'], 'action': 'Ask the store to correct the receipt; signing is blocked.'})
            sums[ln['lot']] = sums.get(ln['lot'], 0) + ln['qty']
    for lot, s in sums.items():
        if lot in received and s > received[lot]:
            out.append({'rule': 'over_shipped', 'lot': lot, 'shipped': s, 'received': received[lot], 'action': 'Signing is blocked until the numbers are corrected.'})
    return out


def recall_problems(contacts):
    """contacts: [{customer, received, destroyed, sold}] from the stores' destruction forms."""
    out = []
    for c in contacts:
        if c.get('destroyed') is None:
            continue
        if c['destroyed'] + c['sold'] != c['received']:
            out.append({'rule': 'evidence_does_not_add_up', 'customer': c['customer'], 'received': c['received'], 'destroyed': c['destroyed'], 'sold': c['sold'],
                        'action': 'Evidence cannot be confirmed; ask the store to correct the form.'})
    return out
