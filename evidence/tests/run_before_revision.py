"""Re-runs the four harmful-error / boundary cases against the version BEFORE the evaluation
revisions (v14, kept in evidence/tests/v14_before_revision.html) to show what the tests caught.
    python3 evidence/tests/run_before_revision.py
"""
import json, os
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1400, 'height': 900})
    pg.route('**/fonts.googleapis.com/**', lambda r: r.abort())
    def click(t, i=0): pg.get_by_role('button', name=t, exact=True).nth(i).click(); pg.wait_for_timeout(120)
    def sig(name):
        pg.fill('#sigName', name); pg.locator('#sigpad').scroll_into_view_if_needed(); bx = pg.locator('#sigpad').bounding_box()
        pg.mouse.move(bx['x'] + 40, bx['y'] + 100); pg.mouse.down(); pg.mouse.move(bx['x'] + 300, bx['y'] + 60); pg.mouse.up(); pg.check('#sigOk'); pg.wait_for_timeout(100)
        return pg.evaluate("document.getElementById('signBtn').disabled")
    pg.goto('file://' + os.path.join(HERE, 'v14_before_revision.html')); pg.wait_for_timeout(300); pg.evaluate('S.auto=false')
    click('Upload all'); pg.wait_for_timeout(2600); click('Confirm and continue →'); click('Check for problems →'); click('Review problems →')
    pg.evaluate("var c=C(); SC.s2.lines[1].realLot='RC-ENG-1109-02'; lotOf(c,'m1').stage='gotlot'; render0()")
    out['U3'] = 'apply available: %s' % (pg.get_by_role('button', name='Verify and apply lot code', exact=True).count() > 0)
    pg.goto('file://' + os.path.join(HERE, 'v14_before_revision.html')); pg.wait_for_timeout(300); pg.evaluate('S.auto=false')
    click('Upload all'); pg.wait_for_timeout(2600); click('Confirm and continue →'); click('Check for problems →'); click('Review problems →')
    pg.get_by_role('button', name='48 CS').click(); click('Dock count'); click('Save decision'); click('Draft supplier request'); click('Send request')
    pg.evaluate("playNext()"); click('Send follow-up'); pg.evaluate("playNext()"); pg.evaluate("openCase(mainCase().id)")
    click('Verify and apply lot code'); click('Continue to sign-off →'); sig('Maria Lopez'); click('Sign and complete'); pg.evaluate("playNext()"); pg.evaluate("set({view:'ship'})")
    pg.evaluate("OUT[2].lines[0][1]='RC-SLC-1109-01'; render0()"); t = pg.inner_text('#app')
    out['U5'] = 'line shown as matched: %s; sign disabled: %s' % (t.count('✓ TR-2026-0420') == 5, sig('Ana Ruiz'))
    pg.evaluate("OUT[2].lines[0][1]='RC-SLC-1109-07'; OUT[0].lines[1][2]=22; S.shipCase.sigPts=[]; render0()"); t = pg.inner_text('#app')
    out['U6'] = 'balance chips all "Balances": %s; sign disabled: %s' % (t.count('Balances') == 2, sig('Ana Ruiz'))
    pg.evaluate("""(function(){ newInc(now()); S.inc.fda.sentTs = now(); var rows = {}; CUST.forEach(function(cu){ rows[cu.c] = {st:'replied', calls:[], overdue:false, replyTs: now()}; });
        S.inc.recall = {noticeTs: now(), flagged: true, rows: rows, repDraft:false, repTs:0, ackTs:0}; CUST[1].destroyed = 12; set({view:'incident'}); })()""")
    out['U8'] = 'confirm buttons: %d of 3' % pg.get_by_role('button', name='Confirm evidence', exact=True).count()
    b.close()
json.dump(out, open(os.path.join(HERE, 'before_revision_results.json'), 'w'), indent=1)
print(out)
