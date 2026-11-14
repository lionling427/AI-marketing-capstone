"""End-to-end check: plays the whole TraceReady story in a headless browser, then checks the database.

    python3 backend/app.py              (in one terminal)
    python3 frontend/tests/e2e_story.py (in another; needs: pip install playwright && playwright install chromium)

Takes about 4 minutes, because story events wait 3-5 seconds each.
"""
import csv, io, json, os, urllib.request
from playwright.sync_api import sync_playwright

BASE = os.environ.get('BASE', 'http://localhost:8000')


def api(path):
    return urllib.request.urlopen(BASE + path).read().decode('utf-8')


with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':900})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.route('**/fonts.googleapis.com/**',lambda r:r.abort())
    pg.goto(BASE + '/'); pg.wait_for_function('window.TR && TR.ready'); print('online', pg.evaluate('TR.online'))
    def click(txt,i=0): pg.get_by_role('button',name=txt,exact=True).nth(i).click(); pg.wait_for_timeout(120)
    def wait(): pg.wait_for_timeout(5600)
    def ev(): return pg.evaluate('S.ev')
    def sign(name, btn='Sign and complete'):
        pg.fill('#sigName',name); pg.locator('#sigpad').scroll_into_view_if_needed(); box=pg.locator('#sigpad').bounding_box()
        pg.mouse.move(box['x']+40,box['y']+100); pg.mouse.down(); pg.mouse.move(box['x']+300,box['y']+60); pg.mouse.up(); pg.check('#sigOk'); click(btn)
    click('Upload all'); pg.wait_for_timeout(2600); click('Confirm and continue →'); click('Check for problems →'); click('Review problems →')
    pg.get_by_role('button',name='48 CS').click(); click('Dock count'); click('Save decision'); click('Draft supplier request'); click('Send request')
    pg.wait_for_timeout(1500)
    wait(); print('after auto1', ev())
    click('Send follow-up'); wait(); print('after auto2', ev())
    click('Verify and apply lot code'); click('Continue to sign-off →'); sign('Maria Lopez')
    wait(); print('ship case', ev()); pg.get_by_role('button',name='Go there →').click(); pg.wait_for_timeout(200); sign('Ana Ruiz', 'Sign and link to TR-2026-0420'); wait(); print('after ship+fda', ev()); pg.get_by_role('button',name='Go there →').click(); pg.wait_for_timeout(200)
    click('Build FDA spreadsheet'); click('Send to FDA'); wait(); print('recall', ev())
    click('Block this lot (no receiving or shipping)'); click('Send recall notice to all')
    wait(); wait(); wait(); print('replies', ev())
    pg.locator('text=Recall response sheet').scroll_into_view_if_needed(); 
    click('Log call',2); click('Reached, will act today'); click('Save call'); wait(); print('sunset', ev())
    for i in range(3):
        btn=pg.get_by_role('button',name='Confirm evidence',exact=True)
        if btn.count(): btn.first.click(); pg.wait_for_timeout(150)
    click('Build recall report'); click('Send to Rio Claro'); wait(); print('ack', ev())
    sign('Maria Lopez'); print('closed', pg.evaluate('!!S.inc.closed'))
    pg.get_by_role('button',name='History',exact=True).click(); pg.wait_for_timeout(200); pg.get_by_role('button',name='View',exact=True).nth(2).click(); pg.wait_for_timeout(200); pg.get_by_role('button',name='Shipping tab (5)').click(); pg.wait_for_timeout(200); 
    pg.wait_for_timeout(1500)
    import json
    fr=pg.evaluate('fdaRows()'); 
    print('inbox', pg.evaluate('TR.inbox.length'))
    assert not errs, errs; b.close()

open_cases = [(c['id'], c['status']) for c in json.loads(api('/api/cases')) if c['status'] != 'complete']
assert sorted(open_cases) == [('TR-2026-0412', 'pending'), ('TR-2026-0415', 'pending')], open_cases
assert sorted(s['step'] for s in json.loads(api('/api/signatures'))) == ['incident', 'receiving', 'shipping']
assert len(json.loads(api('/api/inbox'))) == 11 and len(json.loads(api('/api/extractions'))) == 9
lot = json.loads(api('/api/trace/RC-SLC-1109-07'))['lot']
assert (lot['received_qty'], lot['shipped_qty'], lot['status']) == (48, 48, 'recalled'), lot
for cte, key in (('receiving', 'rr'), ('shipping', 'sr')):
    rows = list(csv.reader(io.StringIO(api('/api/export/fda.csv?cte=%s&case=TR-2026-0420' % cte))))[1:]
    assert rows == [[str(x) for x in r] for r in fr[key]], cte + ' export differs from the screen'
print('All checks passed: story completed, database and FDA export match the screen.')
