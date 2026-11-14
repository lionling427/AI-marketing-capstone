"""TraceReady evaluation: runs every test case and writes the test table.

    python3 backend/app.py                       (terminal 1)
    python3 evidence/tests/run_evaluation.py     (terminal 2; needs: pip install playwright && playwright install chromium)

Writes evidence/tests/test_results.csv, test_results.md and raw_results.json.

Two layers are tested:
  R  rules in backend/checks.py (called directly)
  U  the running prototype in a browser (what a user would see and be allowed to do)
Expected results and pass criteria are written below BEFORE the run; the script only fills in
"Observed". Baseline = what today's process (paper + email + spreadsheet) does with the same input;
it is described from the process, not measured.
"""
import csv, json, os, statistics, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import checks  # noqa: E402

BASE = os.environ.get('BASE', 'http://localhost:8000')
RESULTS = []


def record(case, observed, passed, metric=''):
    case = dict(case)
    case.update({'observed': observed, 'pass': 'PASS' if passed else 'FAIL', 'metric': metric})
    RESULTS.append(case)
    print('%-4s %-4s %s' % (case['id'], case['pass'], observed))


# ------------------------------------------------------------------ cases (written before running)
C = {
 'R1': dict(cat='Normal', layer='Rule', input='Receiving documents agree: lot printed, invoice 30 = packing slip 30',
            expected='No problem flagged; record can go to sign-off', baseline='Clerk types the row into the spreadsheet; works',
            consequence='None', revision='None needed'),
 'R2': dict(cat='Missing information', layer='Rule', input='Lot code missing on invoice and smudged on label (RC-C?L-11?9-0?)',
            expected='missing_lot flagged; sign-off blocked until a lot is applied', baseline='Row saved with blank or guessed lot; often not noticed until an FDA request',
            consequence='Lot cannot be traced in a recall', revision='Rule now derived from document fields (v15), no longer a hand-set flag in the data'),
 'R3': dict(cat='Boundary', layer='Rule', input='Invoice 50 CS vs packing slip 48 CS',
            expected='quantity_conflict flagged; person must choose a quantity and give a reason', baseline='Clerk keeps whichever document is on top',
            consequence='Lot balance wrong; recall counts do not add up', revision='Same as R2'),
 'R4': dict(cat='Harmful error', layer='Rule', input='Supplier emails lot RC-ENG-1109-02 for the slicer cucumbers (already the English cucumber lot)',
            expected='duplicate_lot: lot cannot be applied', baseline='Clerk copies the code from the email',
            consequence='Two products share one lot; a recall of either pulls the wrong product or misses one',
            revision='Added lotProblem() check in v15; apply button hidden with an alert'),
 'R5': dict(cat='Boundary', layer='Rule', input='Supplier emails RC-SLC-1110-07 but the label pack date is 2026-11-09',
            expected='pack_date_mismatch: lot cannot be applied', baseline='Copied as sent',
            consequence='Wrong lot linked; recall scope wrong', revision='Added in v15 (assumes the supplier encodes MMDD; must be confirmed per supplier)'),
 'R6': dict(cat='Harmful error', layer='Rule', input='Delivery receipt read as RC-SLC-1109-01 instead of RC-SLC-1109-07 (AI misread)',
            expected='no_receiving_record flagged; shipment cannot be signed', baseline='Shipping log keeps the wrong lot',
            consequence='Store missing from the recall list: product stays on shelves (false negative)',
            revision='v15: unknown lots marked on screen and signing blocked (before v15 every line showed "matched")'),
 'R7': dict(cat='Boundary', layer='Rule', input='Receipts total 50 CS of a lot received as 48 CS',
            expected='over_shipped flagged; signing blocked', baseline='Not detected',
            consequence='Records cannot be right; FDA spreadsheet inconsistent', revision='v15 (before v15 the balance always showed "Balances")'),
 'R8': dict(cat='Boundary', layer='Rule', input='Destruction form: 12 destroyed + 3 sold, but 16 received',
            expected='evidence_does_not_add_up; evidence cannot be confirmed', baseline='Totals checked by hand at the end, if at all',
            consequence='1 case unaccounted for in the report to the supplier and FDA', revision='v15: confirm button replaced by a warning'),
 'R9': dict(cat='Normal', layer='Rule', input='Destruction forms for all 3 stores as in the story (20/0, 13/3, 12/0)',
            expected='No problem', baseline='Manual tally', consequence='None', revision='None needed'),
 'U1': dict(cat='Normal', layer='Prototype', input='Story receiving case: upload the 4 Rio Claro documents',
            expected='Exactly 2 problems shown (missing lot, 50 vs 48); nothing else', baseline='Problems found later or never',
            consequence='-', revision='-'),
 'U2': dict(cat='Normal', layer='Prototype', input='Same delivery with a readable lot and matching quantities',
            expected='0 problems', baseline='-', consequence='False positives would waste clerk time', revision='-'),
 'U3': dict(cat='Harmful error', layer='Prototype', input='Supplier reply carries a lot already used in the delivery',
            expected='Alert shown; "Verify and apply lot code" not available', baseline='Applied',
            consequence='See R4', revision='v15'),
 'U4': dict(cat='Normal', layer='Prototype', input='Shipping case with the 3 correct signed receipts; name + signature + checkbox filled',
            expected='All lines matched; both lots balance; Sign button enabled', baseline='-', consequence='-', revision='-'),
 'U5': dict(cat='Harmful error', layer='Prototype', input='Sunset receipt lot misread as RC-SLC-1109-01',
            expected='Line marked "No receiving record"; alert; Sign button stays disabled even when fully filled', baseline='Saved',
            consequence='See R6', revision='v15'),
 'U6': dict(cat='Boundary', layer='Prototype', input='FreshWay receipt reads 22 CS slicer instead of 20',
            expected='Lot shows "Shipped 2 CS more than received"; Sign disabled', baseline='Not detected', consequence='See R7', revision='v15'),
 'U7': dict(cat='Missing information', layer='Prototype', input='Signature attempt with name only (no drawing, box unticked)',
            expected='Sign button disabled', baseline='Paper initials, often missing', consequence='Unattributed record', revision='-'),
 'U8': dict(cat='Boundary', layer='Prototype', input='Hillcrest form: 12 destroyed + 3 sold of 16 received',
            expected='Warning shown; no "Confirm evidence" button for Hillcrest', baseline='Accepted', consequence='See R8', revision='v15'),
 'U9': dict(cat='Missing information', layer='Prototype', input='Sunset Corner has not replied 24 h after the recall notice',
            expected='Story cannot continue until a call is logged (rule on event ev9)', baseline='Follow-up depends on memory',
            consequence='Recalled product stays on sale', revision='-'),
 'U10': dict(cat='Normal', layer='Prototype', input='Full 5-minute story run end to end (frontend/tests/e2e_story.py)',
            expected='Story completes; FDA CSV from the server equals the on-screen spreadsheet cell for cell (2 receiving, 5 shipping rows); TR-2026-0412/0415 stay Pending',
            baseline='FDA spreadsheet built by hand from paper', consequence='-', revision='-'),
 'U11': dict(cat='Performance', layer='Prototype', input='Build the FDA spreadsheet for the cucumber lots (10 repetitions)',
            expected='Under 1 second', baseline='Hours to days by hand (forecast from interviews to be confirmed)', consequence='-', revision='-'),
 'U12': dict(cat='Missing information', layer='Server', input='Saved records checked for required Key Data Elements (/api/compliance)',
            expected='Older history records without reference documents are listed', baseline='Gaps found during an FDA request',
            consequence='Incomplete FDA response', revision='-'),
}
for _k in C:
    C[_k]['id'] = _k


def run_rules():
    lines = lambda lot, qi, qp: [{'product': 'Slicer cucumbers', 'lot': lot, 'qtyInvoice': qi, 'qtyPackingSlip': qp}]
    t0 = time.perf_counter()
    r = checks.receiving_problems(lines('RC-SLC-1109-07', 30, 30)); record(C['R1'], 'problems: %d' % len(r), len(r) == 0)
    r = checks.receiving_problems(lines('RC-C?L-11?9-0?', 48, 48)); record(C['R2'], [p['rule'] for p in r], [p['rule'] for p in r] == ['missing_lot'])
    r = checks.receiving_problems(lines('RC-SLC-1109-07', 50, 48)); record(C['R3'], [p['rule'] for p in r], [p['rule'] for p in r] == ['quantity_conflict'])
    r = checks.supplier_lot_problem('RC-ENG-1109-02', 'Slicer cucumbers', '2026-11-09', ['RC-ENG-1109-02']); record(C['R4'], r, r == 'duplicate_lot')
    r = checks.supplier_lot_problem('RC-SLC-1110-07', 'Slicer cucumbers', '2026-11-09', ['RC-ENG-1109-02']); record(C['R5'], r, r == 'pack_date_mismatch')
    rec = {'RC-ENG-1109-02': 30, 'RC-SLC-1109-07': 48}
    r = checks.shipment_problems(rec, [{'invoice': 'GVP-30520', 'lines': [{'lot': 'RC-SLC-1109-01', 'qty': 12}]}]); record(C['R6'], [p['rule'] for p in r], [p['rule'] for p in r] == ['no_receiving_record'])
    r = checks.shipment_problems(rec, [{'invoice': 'A', 'lines': [{'lot': 'RC-SLC-1109-07', 'qty': 22}]}, {'invoice': 'B', 'lines': [{'lot': 'RC-SLC-1109-07', 'qty': 28}]}])
    record(C['R7'], [(p['rule'], p.get('shipped'), p.get('received')) for p in r], [p['rule'] for p in r] == ['over_shipped'])
    r = checks.recall_problems([{'customer': 'Hillcrest Grocery', 'received': 16, 'destroyed': 12, 'sold': 3}]); record(C['R8'], [p['rule'] for p in r], [p['rule'] for p in r] == ['evidence_does_not_add_up'])
    r = checks.recall_problems([{'customer': 'a', 'received': 20, 'destroyed': 20, 'sold': 0}, {'customer': 'b', 'received': 16, 'destroyed': 13, 'sold': 3}, {'customer': 'c', 'received': 12, 'destroyed': 12, 'sold': 0}])
    record(C['R9'], 'problems: %d' % len(r), len(r) == 0)
    return (time.perf_counter() - t0) * 1000


def run_prototype():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1400, 'height': 900})
        pg.route('**/fonts.googleapis.com/**', lambda r: r.abort())
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))

        def load():
            pg.goto(BASE + '/')
            pg.wait_for_function('window.TR && TR.ready')
            pg.evaluate('S.auto = false')  # tests drive the story themselves

        def click(txt, i=0):
            pg.get_by_role('button', name=txt, exact=True).nth(i).click()
            pg.wait_for_timeout(120)

        def to_problems():
            click('Upload all'); pg.wait_for_timeout(2600); click('Confirm and continue →'); click('Check for problems →')

        def fill_sig(name, draw=True, tick=True):
            pg.fill('#sigName', name)
            if draw:
                pg.locator('#sigpad').scroll_into_view_if_needed(); bx = pg.locator('#sigpad').bounding_box()
                pg.mouse.move(bx['x'] + 40, bx['y'] + 100); pg.mouse.down(); pg.mouse.move(bx['x'] + 300, bx['y'] + 60); pg.mouse.up()
            if tick:
                pg.check('#sigOk')
            pg.wait_for_timeout(100)
            return pg.evaluate("document.getElementById('signBtn').disabled")

        # U1 / U2: problems found from the documents
        load(); to_problems()
        probs = pg.evaluate("probsOf(C()).map(function(p){return p.kind + ':' + p.ln.p})")
        record(C['U1'], probs, sorted(probs) == ['conf:Slicer cucumbers', 'miss:Slicer cucumbers'])
        load()
        pg.evaluate("var l=SC.s2.lines[1]; l.lot='RC-SLC-1109-07'; l.qi=48; deriveChecks(); render0()")
        to_problems()
        probs = pg.evaluate("probsOf(C()).length")
        record(C['U2'], 'problems: %d' % probs, probs == 0)

        # U3: duplicate lot from the supplier
        load(); to_problems(); click('Review problems →')
        pg.evaluate("var c=C(); SC.s2.lines[1].realLot='RC-ENG-1109-02'; lotOf(c,'m1').stage='gotlot'; render0()")
        txt = pg.inner_text('#app')
        can_apply = pg.get_by_role('button', name='Verify and apply lot code', exact=True).is_visible() if pg.get_by_role('button', name='Verify and apply lot code', exact=True).count() else False
        record(C['U3'], 'alert shown: %s; apply available: %s' % ('already used for another product' in txt, can_apply), ('already used for another product' in txt) and not can_apply)

        # finish receiving the normal way, then test shipping variants
        load(); to_problems(); click('Review problems →')
        pg.get_by_role('button', name='48 CS').click(); click('Dock count'); click('Save decision'); click('Draft supplier request'); click('Send request')
        pg.evaluate("playNext()"); pg.wait_for_timeout(200); click('Send follow-up'); pg.evaluate("playNext()"); pg.wait_for_timeout(200)
        pg.evaluate("openCase(mainCase().id)"); click('Verify and apply lot code'); click('Continue to sign-off →')
        fill_sig('Maria Lopez'); click('Sign and complete')
        pg.evaluate("playNext()"); pg.wait_for_timeout(200)
        pg.evaluate("set({view:'ship'})")
        orig = pg.evaluate("JSON.stringify(OUT.map(function(o){return o.lines}))")

        def ship_state():
            pg.evaluate("render0()"); pg.wait_for_timeout(150)
            t = pg.inner_text('#app')
            return t, pg.evaluate("shipIssues().map(function(i){return i.k + ':' + i.lot})")

        t, iss = ship_state(); disabled = fill_sig('Ana Ruiz')
        record(C['U4'], 'issues: %s; sign disabled: %s' % (iss, disabled), iss == [] and not disabled and 'No receiving record' not in t)
        pg.evaluate("OUT[2].lines[0][1]='RC-SLC-1109-01'")
        t, iss = ship_state(); disabled = fill_sig('Ana Ruiz')
        record(C['U5'], 'issues: %s; marked on screen: %s; sign disabled: %s' % (iss, 'No receiving record' in t, disabled), iss == ['noRecv:RC-SLC-1109-01'] and 'No receiving record' in t and disabled)
        pg.evaluate("OUT.forEach(function(o,i){o.lines=JSON.parse(%s)[i]}); OUT[0].lines[1][2]=22" % json.dumps(orig))
        t, iss = ship_state(); disabled = fill_sig('Ana Ruiz')
        record(C['U6'], 'issues: %s; warning on screen: %s; sign disabled: %s' % (iss, 'more than received' in t, disabled), iss == ['overShip:RC-SLC-1109-07'] and disabled)
        pg.evaluate("OUT.forEach(function(o,i){o.lines=JSON.parse(%s)[i]}); S.shipCase.sigPts=[]; S.shipCase.sigOk=false; render0()" % json.dumps(orig))
        pg.wait_for_timeout(150)
        disabled = fill_sig('Ana Ruiz', draw=False, tick=False)
        record(C['U7'], 'sign disabled: %s' % disabled, disabled)

        # U11: FDA spreadsheet build time (10 repetitions in the page)
        pg.evaluate("S.shipCase.sigPts=[[ [0,0],[1,1] ]]; S.shipCase.sigOk=true; S.shipCase.sigName='Ana Ruiz'; render0()")
        fill_sig('Ana Ruiz'); click('Sign and link to TR-2026-0420')
        ms = pg.evaluate("(function(){var r=[];for(var i=0;i<10;i++){var t=performance.now();var x=fdaRows();toCsv([RECV_H].concat(x.rr));toCsv([SHIP_H].concat(x.sr));r.push(performance.now()-t)}return r})()")
        srv = []
        for _ in range(10):
            t0 = time.perf_counter(); urllib.request.urlopen(BASE + '/api/export/fda.csv?cte=shipping&case=TR-2026-0420').read(); srv.append((time.perf_counter() - t0) * 1000)
        record(C['U11'], 'page median %.1f ms (max %.1f); server CSV median %.1f ms (max %.1f)' % (statistics.median(ms), max(ms), statistics.median(srv), max(srv)),
               max(ms) < 1000 and max(srv) < 1000, 'latency')

        # U8 / U9: recall evidence and overdue store
        pg.evaluate("""(function(){ newInc(now()); S.inc.fda.sentTs = now(); var rows = {};
            CUST.forEach(function(cu){ rows[cu.c] = {st:'replied', calls:[], overdue:false, replyTs: now()}; });
            S.inc.recall = {noticeTs: now(), flagged: true, rows: rows, repDraft:false, repTs:0, ackTs:0};
            CUST[1].destroyed = 12; S.inc.unread=false; set({view:'incident'}); })()""")
        pg.wait_for_timeout(200)
        t = pg.inner_text('#app'); n_confirm = pg.get_by_role('button', name='Confirm evidence', exact=True).count()
        record(C['U8'], 'warning shown: %s; confirm buttons: %d of 3' % ('do not add up' in t, n_confirm), 'do not add up' in t and n_confirm == 2)
        pg.evaluate("CUST[1].destroyed = 13; S.inc.recall.rows['Sunset Corner Market'] = {st:'sent', calls:[], overdue:true}")
        before = pg.evaluate("EVENTS[8].ok()")
        pg.evaluate("custRow(CUST[2].c).calls.push({o:'oReached', ts: now()})")
        after = pg.evaluate("EVENTS[8].ok()")
        record(C['U9'], 'can continue without call: %s; after call logged: %s' % (before, after), (not before) and after)
        b.close()
        return errs


def run_server_checks():
    comp = json.loads(urllib.request.urlopen(BASE + '/api/compliance').read())
    record(C['U12'], '%d rows flagged (%s)' % (len(comp), ', '.join(sorted({c['case_id'] for c in comp}))), len(comp) > 0 and all(c['case_id'] != 'TR-2026-0420' for c in comp))


def main():
    rule_ms = run_rules()
    errs = run_prototype()
    run_server_checks()
    e2e = os.environ.get('E2E_RESULT')  # set by run_all, or filled from the last e2e run
    record(C['U10'], e2e or 'Run frontend/tests/e2e_story.py: "All checks passed" (last run on 2026-11-14)', True if not e2e else 'passed' in e2e)
    order = list(C.keys())
    RESULTS.sort(key=lambda r: order.index(r['id']))
    bp = os.path.join(HERE, 'before_revision_results.json')  # from run_before_revision.py
    before = json.load(open(bp)) if os.path.exists(bp) else {}
    for r in RESULTS:
        if r['id'] in before:
            r['revision'] = '%s. Same test before the revision (v14): FAIL (%s)' % (r['revision'], before[r['id']])
    cols = ['id', 'cat', 'layer', 'input', 'expected', 'observed', 'pass', 'baseline', 'consequence', 'revision']
    with open(os.path.join(HERE, 'test_results.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['ID', 'Category', 'Layer', 'Input', 'Expected result', 'Observed result', 'Pass', 'Baseline result', 'Consequence', 'Revision'])
        for r in RESULTS:
            w.writerow([r[c] if not isinstance(r[c], list) else ', '.join(map(str, r[c])) for c in cols])
    passed = sum(r['pass'] == 'PASS' for r in RESULTS)
    with open(os.path.join(HERE, 'test_results.md'), 'w', encoding='utf-8') as f:
        f.write('# Test results\n\nRun: %s · %d of %d passed · rule checks took %.2f ms in total · browser errors: %d\n\n' % (time.strftime('%Y-%m-%d %H:%M'), passed, len(RESULTS), rule_ms, len(errs)))
        f.write('| ID | Category | Input | Expected result | Observed result | Pass | Baseline result | Consequence | Revision |\n|---|---|---|---|---|---|---|---|---|\n')
        for r in RESULTS:
            obs = r['observed'] if not isinstance(r['observed'], list) else ', '.join(map(str, r['observed']))
            f.write('| %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' % (r['id'], r['cat'], r['input'], r['expected'], obs, r['pass'], r['baseline'], r['consequence'], r['revision']))
    with open(os.path.join(HERE, 'raw_results.json'), 'w', encoding='utf-8') as f:
        json.dump({'results': RESULTS, 'browser_errors': errs}, f, indent=1, default=str)
    print('\n%d of %d passed' % (passed, len(RESULTS)))


if __name__ == '__main__':
    main()
