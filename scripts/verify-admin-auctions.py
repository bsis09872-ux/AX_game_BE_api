"""관리자 경매 조회를 임시 PostgreSQL DB와 실제 Chromium에서 검증한다.

uv run --frozen --with httpx --with playwright python scripts/verify-admin-auctions.py
DATABASE_URL 계정에는 임시 DB 생성 권한이 필요하다. 기존 DB의 데이터는 변경하지 않는다.
"""

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from uuid import uuid4

import asyncpg
from dotenv import load_dotenv
import httpx
from playwright.async_api import async_playwright, expect
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / '.private/admin-auction-qa'
BIG_ID = 9007199254740993


def check(condition, label):
    assert condition, label
    print('PASS:', label, flush=True)


def listing_ids(html):
    return [int(value) for value in re.findall(r'<td><a href="/admin/auctions/(\d+)', html)]


async def ready(base, process):
    async with httpx.AsyncClient() as client:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('검증 서버가 종료되었습니다. .private/admin-auction-qa/server.log 확인')
            with suppress(httpx.TransportError):
                if (await client.get(base + '/health')).status_code == 200:
                    return
            await asyncio.sleep(0.1)
    raise RuntimeError('검증 서버 시작 시간 초과')


async def register(client, login_id):
    password = secrets.token_urlsafe(24)
    response = await client.post('/v1/auth/register', json={
        'login_id': login_id, 'display_name': login_id, 'password': password,
    })
    assert response.status_code == 201, response.text
    identity = int(response.json()['id'])
    response = await client.post('/login', data={'login_id': login_id, 'password': password})
    assert response.status_code == 303
    return identity


async def seed(db, seller, buyer, other):
    now = datetime.now(timezone.utc)
    for identity in range(1, 27):
        state = {22: 'QUEUED', 23: 'BIDDING', 24: 'FAILED', 25: 'CANCELLED'}.get(identity, 'SOLD')
        sold = state == 'SOLD'
        definition = 100 if identity <= 21 else 200
        seller_id, buyer_id = (seller, buyer) if identity <= 25 else (buyer, other)
        await db.execute('''
            INSERT INTO listings(id, seller_id, inventory_item_id, item_definition_id,
                start_price, current_bidder_id, current_bid_amount, status,
                created_at, started_at, ends_at, closed_at, updated_at)
            VALUES ($1,$2,$3,$4,100,$5,$6,$7,$8,$9,$10,$11,$8)
        ''', identity, seller_id, 1000 + identity, definition,
            buyer_id if sold else None, 150 if sold else None, state, now,
            None if state == 'QUEUED' else now - timedelta(minutes=5),
            None if state == 'QUEUED' else now + timedelta(minutes=5),
            now if state in {'SOLD', 'FAILED', 'CANCELLED'} else None)
        if sold:
            await db.execute('''
                INSERT INTO trades(listing_id, seller_id, buyer_id, item_name_snapshot,
                    seller_name_snapshot, buyer_name_snapshot, price_snapshot, completed_at)
                VALUES ($1,$2,$3,$4,$5,$6,150,$7)
            ''', identity, seller_id, buyer_id,
                '<script>window.snapshotXss=1</script>' if identity == 26 else '검증 붕어',
                '거래 당시 판매자', '거래 당시 구매자', now)

    await db.execute('''
        INSERT INTO listings(id,seller_id,inventory_item_id,item_definition_id,start_price,
            status,created_at,updated_at) VALUES ($1,$2,$1,200,100,'QUEUED',$3,$3)
    ''', BIG_ID, seller, now)


async def snapshot(db):
    return {
        table: [tuple(row) for row in await db.fetch(f'SELECT * FROM {table} ORDER BY 1')]
        for table in ('listings', 'trades', 'inventory_items', 'wallets')
    }


async def http_checks(guest, member, admin, buyer, seller):
    paths = ['/admin/auctions', '/admin/auctions/1', '/admin/auction-trades']
    for path in paths:
        for client, expected in ((guest, 303), (member, 403), (admin, 200)):
            response = await client.get(path)
            check(response.status_code == expected, f'{path} permission {expected}')
            if expected == 303:
                assert response.headers['location'].startswith('/login')
            if expected == 200:
                assert response.headers['cache-control'] == 'no-store'
        check((await admin.post(path)).status_code == 405, f'{path} read only')

    response = await admin.get('/admin/auctions')
    check(listing_ids(response.text) == [BIG_ID, *range(26, 7, -1)], 'all statuses, stable order and 20 rows')
    for status, expected in [('QUEUED', [BIG_ID, 22]), ('BIDDING', [23]),
                             ('FAILED', [24]), ('CANCELLED', [25])]:
        response = await admin.get('/admin/auctions', params={'status': status})
        check(listing_ids(response.text) == expected, f'listing status {status}')

    cases = [
        ({'status': 'SOLD', 'item_definition_id': 100}, list(range(21, 1, -1))),
        ({'status': 'SOLD', 'item_definition_id': 100, 'page': 2}, [1]),
        ({'listing_id': 1, 'status': 'SOLD', 'item_definition_id': 100, 'inventory_item_id': 1001}, [1]),
        ({'listing_id': 1, 'status': 'QUEUED'}, []),
        ({'inventory_item_id': 1024}, [24]),
        ({'listing_id': BIG_ID}, [BIG_ID]),
        ({'page': 3}, []),
    ]
    for params, expected in cases:
        response = await admin.get('/admin/auctions', params=params)
        check(response.status_code == 200 and listing_ids(response.text) == expected,
              f'listing filters {params}')
        if params.get('page') == 2:
            assert 'item_definition_id=100&amp;status=SOLD&amp;page=1' in response.text
            assert '>다음</a>' not in response.text

    for identity in [1, 22, 23, 24, 25, BIG_ID]:
        response = await admin.get(f'/admin/auctions/{identity}')
        check(response.status_code == 200 and f'매물 #{identity}' in response.text, f'detail {identity}')
    response = await admin.get('/admin/auctions/99999')
    check(response.status_code == 404 and '찾을 수 없습니다' in response.text, 'detail HTML 404')

    trade_cases = [({}, [26, *range(21, 2, -1)]),
                   ({'listing_id': 1}, [1]), ({'buyer_id': buyer, 'seller_id': seller}, list(range(21, 1, -1))),
                   ({'buyer_id': buyer, 'seller_id': seller, 'page': 2}, [1]),
                   ({'buyer_id': seller}, []), ({'seller_id': buyer}, [26]),
                   ({'listing_id': 1, 'buyer_id': buyer, 'seller_id': seller}, [1]),
                   ({'listing_id': 22}, [])]
    for params, expected in trade_cases:
        response = await admin.get('/admin/auction-trades', params=params)
        check(response.status_code == 200 and listing_ids(response.text) == expected,
              f'trade filters {params}')
        if expected:
            assert '거래 당시 판매자' in response.text
        if 26 in expected:
            assert '&lt;script&gt;' in response.text
        if params.get('page') == 2:
            assert f'buyer_id={buyer}&amp;seller_id={seller}&amp;page=1' in response.text
            assert '>다음</a>' not in response.text

    fields = {'/admin/auctions': ['listing_id', 'item_definition_id', 'inventory_item_id'],
              '/admin/auction-trades': ['listing_id', 'buyer_id', 'seller_id']}
    for path, names in fields.items():
        for field in [*names, 'page']:
            for value in ['0', '-1', 'abc', '1.5', '9223372036854775808']:
                response = await admin.get(path, params={field: value})
                assert response.status_code == 422, (path, field, value)
        response = await admin.get(path, params={name: '' for name in names})
        assert response.status_code == 200
    for value in ['', 'INVALID']:
        response = await admin.get('/admin/auctions', params={'status': value})
        assert response.status_code == (200 if value == '' else 422)
    for value in ['0', '-1', 'abc', '9223372036854775808']:
        assert (await admin.get('/admin/auctions/' + value)).status_code == 422
    check(True, 'empty filters and invalid query/path bounds')


async def browser_checks(base, admin, buyer, seller):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        await context.add_cookies([{'name': c.name, 'value': c.value, 'url': base} for c in admin.cookies.jar])
        page = await context.new_page()
        errors, documents = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda req: documents.append(req.url) if req.resource_type == 'document' else None)
        await page.goto(base + '/admin')
        await page.evaluate('''() => {
            window.shell = [document.querySelector('header'), document.querySelector('.admin-tabs'),
                document.querySelector('#main-content'), document.querySelector('.title-carousel')];
        }''')
        await page.locator('[data-admin-tab="auctions"]').click()
        await expect(page.locator('.admin-section h2')).to_have_text('전체 매물')
        await expect(page.locator('tbody tr')).to_have_count(20)
        await page.evaluate('window.scrollTo(0, 0)')
        await page.screenshot(path=str(ARTIFACTS / 'listings-desktop.png'), full_page=True)
        await page.locator('[name="status"]').select_option('SOLD')
        await page.locator('[name="item_definition_id"]').fill('100')
        await page.get_by_role('button', name='조회', exact=True).click()
        await expect(page).to_have_url(re.compile(r'item_definition_id=100.*status=SOLD'))
        await expect(page.locator('tbody tr')).to_have_count(20)
        await page.get_by_role('link', name='다음', exact=True).click()
        await expect(page.locator('tbody tr')).to_have_count(1)
        await expect(page.locator('.admin-pagination')).to_contain_text('2 페이지')
        await page.locator('tbody td:first-child a').click()
        await expect(page.locator('h3').first).to_contain_text('매물 #1')
        await page.get_by_role('link', name='← 매물 목록').click()
        await expect(page.locator('.admin-pagination')).to_contain_text('2 페이지')
        await expect(page.locator('[name="status"]')).to_have_value('SOLD')
        await page.go_back()
        await expect(page.locator('h3').first).to_contain_text('매물 #1')
        await page.go_forward()
        await expect(page.locator('.admin-pagination')).to_contain_text('2 페이지')
        check(True, 'listing form, pagination, detail return, back/forward preserve filters')

        await page.get_by_role('link', name='초기화', exact=True).click()
        await expect(page).to_have_url(base + '/admin/auctions')
        await page.locator('[name="listing_id"]').fill(str(BIG_ID))
        await page.get_by_role('button', name='조회', exact=True).click()
        await expect(page).to_have_url(re.compile(f'listing_id={BIG_ID}'))
        await expect(page.locator('tbody tr')).to_have_count(1)
        await expect(page.locator('tbody td:first-child')).to_have_text(f'#{BIG_ID}')
        await page.locator('tbody td:first-child a').click()
        await expect(page.locator('h3').first).to_contain_text(str(BIG_ID))
        check(True, '64-bit ID survives browser form and detail link')

        await page.locator('[data-admin-tab="trades"]').click()
        await expect(page.locator('.admin-section h2')).to_have_text('거래 내역')
        await expect(page.locator('[data-admin-tab="trades"]')).to_have_attribute('aria-current', 'page')
        await expect(page.locator('tbody tr').first.locator('td').nth(2)).to_have_text(
            '<script>window.snapshotXss=1</script>')
        assert await page.evaluate('window.snapshotXss === undefined')
        await page.locator('[name="buyer_id"]').fill(str(buyer))
        await page.locator('[name="seller_id"]').fill(str(seller))
        await page.get_by_role('button', name='조회', exact=True).click()
        await expect(page).to_have_url(re.compile(f'buyer_id={buyer}&seller_id={seller}'))
        await expect(page.locator('tbody tr')).to_have_count(20)
        await page.get_by_role('link', name='다음', exact=True).click()
        await expect(page.locator('tbody tr')).to_have_count(1)
        await expect(page.locator('[name="buyer_id"]')).to_have_value(str(buyer))
        assert await page.evaluate('window.snapshotXss === undefined')
        await page.evaluate('window.scrollTo(0, 0)')
        await page.screenshot(path=str(ARTIFACTS / 'trades-desktop.png'), full_page=True)
        await page.locator('tbody td:nth-child(2) a').click()
        await expect(page.locator('h3').first).to_contain_text('매물 #1')
        await page.get_by_role('link', name='이 매물의 거래 내역').click()
        await expect(page.locator('tbody tr')).to_have_count(1)
        await expect(page.locator('[name="listing_id"]')).to_have_value('1')
        await page.locator('tbody td:nth-child(4) a').click()
        await expect(page).to_have_url(base + f'/admin/members/{seller}')
        await expect(page.locator('[data-admin-tab="members"]')).to_have_attribute('aria-current', 'page')
        await page.go_back()
        await expect(page.locator('[name="listing_id"]')).to_have_value('1')
        check(True, 'trade filters, pagination, snapshots and listing links')

        assert await page.evaluate('''() => shell.every((node, i) => node === [
            document.querySelector('header'), document.querySelector('.admin-tabs'),
            document.querySelector('#main-content'), document.querySelector('.title-carousel')][i])''')
        check(len(documents) == 1 and not errors, 'persistent shell, no extra document loads or JS errors')
        await page.set_viewport_size({'width': 390, 'height': 844})
        for tab in ['auctions', 'trades']:
            await page.locator(f'[data-admin-tab="{tab}"]').click()
            await expect(page.locator('.admin-section h2')).to_have_text('전체 매물' if tab == 'auctions' else '거래 내역')
            assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert await page.locator('tbody td').first.evaluate(
                "cell => getComputedStyle(cell).whiteSpace === 'nowrap'")
            await page.screenshot(path=str(ARTIFACTS / f'{tab}-mobile.png'), full_page=True)
        check(True, '390px mobile pages keep table overflow inside its scroll area')
        # JavaScript 없이도 빈 검색 항목과 일반 GET 링크를 처리해야 한다.
        plain = await browser.new_context(java_script_enabled=False)
        await plain.add_cookies(await context.cookies())
        no_js = await plain.new_page()
        await no_js.goto(base + '/admin/auctions')
        await no_js.locator('[name="status"]').select_option('FAILED')
        await no_js.get_by_role('button', name='조회', exact=True).click()
        await expect(no_js.locator('tbody tr')).to_have_count(1)
        await expect(no_js.locator('tbody td:first-child')).to_have_text('#24')
        check(True, 'ordinary HTML form works without JavaScript')
        await browser.close()


async def main():
    load_dotenv(ROOT / '.env.local')
    load_dotenv(ROOT / '.env')
    url = make_url(os.environ['DATABASE_URL'])
    args = dict(user=url.username, password=url.password, host=url.host,
                port=url.port or 5432, database=url.database)
    owner = await asyncpg.connect(**args)
    database_name = 'ax_admin_qa_' + uuid4().hex
    assert re.fullmatch(r'ax_admin_qa_[0-9a-f]{32}', database_name)
    await owner.execute(f'CREATE DATABASE "{database_name}"')
    process, db, log = None, None, None
    clients = []
    try:
        db = await asyncpg.connect(**{**args, 'database': database_name})
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'DATABASE_URL': url.set(database=database_name).render_as_string(hide_password=False),
               'WEB_ORIGIN': base, 'JWT_SECRET_KEY': secrets.token_urlsafe(48)}
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        log = (ARTIFACTS / 'server.log').open('w', encoding='utf-8')
        process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', 'src',
             '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env,
            stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        await ready(base, process)
        clients = [httpx.AsyncClient(base_url=base, headers={'Origin': base}) for _ in range(4)]
        guest, member, admin, other = clients
        seller = await register(member, 'qa_seller')
        buyer = await register(admin, 'qa_admin')
        other_id = await register(other, 'qa_other')
        await db.execute("UPDATE users SET role='ADMIN' WHERE id=$1", buyer)
        for path in ['/admin/auctions', '/admin/auction-trades']:
            response = await admin.get(path)
            check(response.status_code == 200 and '조건에 맞는' in response.text, f'{path} empty state')
        await seed(db, seller, buyer, other_id)
        from verify_admin_cancel import verify_migration, verify_cancellation
        await verify_migration(db, env)
        # 공통 헤더가 최초 방문 때 만드는 관리자 지갑을 조회 비교 전에 준비한다.
        assert (await admin.get('/wallet/balance')).status_code == 200
        before = await snapshot(db)
        await http_checks(guest, member, admin, buyer, seller)
        await browser_checks(base, admin, buyer, seller)
        check(before == await snapshot(db), 'all reads preserve listings, trades, inventory and wallets')
        from verify_admin_domains import verify_admin_domains
        await verify_admin_domains(base, guest, member, admin, seller)
        await verify_cancellation(base, db, guest, member, admin, seller, buyer, env)
        await db.execute("UPDATE users SET role='USER' WHERE id=$1", buyer)
        assert (await admin.post('/admin/listings/1/cancel')).status_code == 403
        for path in ['/admin/auctions', '/admin/auctions/1', '/admin/auction-trades']:
            assert (await admin.get(path)).status_code == 403
        check(True, 'existing session loses access immediately after admin demotion')
        print('ALL PASS: real PostgreSQL, HTTP authentication and Chromium', flush=True)
    finally:
        for client in clients:
            await client.aclose()
        if process:
            process.terminate()
            with suppress(subprocess.TimeoutExpired):
                await asyncio.to_thread(process.wait, 5)
            if process.poll() is None:
                process.kill()
                await asyncio.to_thread(process.wait)
        if log:
            log.close()
        if db:
            await db.close()
        await owner.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        await owner.close()


if __name__ == '__main__':
    asyncio.run(main())
