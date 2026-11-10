"""verify-admin-auctions.py의 임시 DB에서만 실행하는 실제 취소/브라우저 검증."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

from playwright.async_api import async_playwright, expect


ROOT = Path(__file__).resolve().parents[1]


async def run_migration(env):
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / 'scripts/migrate-auction-admin-cancel.py'),
        cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode(errors='replace')
    return stdout


async def verify_migration(db, env):
    # 이 연결은 호출자가 만든 무작위 이름의 검증 DB여야 한다.
    assert (await db.fetchval('SELECT current_database()')).startswith('ax_admin_qa_')
    before = await db.fetch('SELECT id,status,start_price FROM listings ORDER BY id')
    await db.execute('ALTER TABLE listings DROP COLUMN admin_cancelled_by')
    await run_migration(env)
    await run_migration(env)
    assert before == await db.fetch('SELECT id,status,start_price FROM listings ORDER BY id')
    columns = await db.fetch('''SELECT column_name,data_type,character_maximum_length,is_nullable
        FROM information_schema.columns WHERE table_name='listings' AND column_name LIKE 'admin_cancel%'
        ORDER BY column_name''')
    assert [tuple(row) for row in columns] == [
        ('admin_cancelled_by', 'bigint', None, 'YES'),
    ]
    # 이전 버전의 사유 컬럼과 기록이 있어도 마이그레이션은 보존한다.
    await db.execute("ALTER TABLE listings ADD COLUMN admin_cancel_reason VARCHAR(200) NULL")
    await db.execute("UPDATE listings SET admin_cancel_reason='legacy audit' WHERE id=1")
    await run_migration(env)
    assert await db.fetchval('SELECT admin_cancel_reason FROM listings WHERE id=1') == 'legacy audit'
    print('PASS migration: existing rows, legacy audit and repeat application preserved', flush=True)


async def verify_cancellation(base, db, guest, member, admin, seller, admin_id, env):
    bearer = lambda client: {'Authorization': 'Bearer ' + client.cookies.get('access_token')}

    async def state(listing_id):
        return await db.fetchrow('SELECT * FROM listings WHERE id=$1', listing_id)

    async def snapshot():
        return {table: await db.fetch(f'SELECT * FROM {table} ORDER BY 1')
                for table in ['listings', 'inventory_items', 'item_events', 'wallets', 'trades']}

    async def cancel(listing_id, client=admin):
        return await client.post(f'/admin/listings/{listing_id}/cancel')

    async def group(size=1):
        number = await db.fetchval('SELECT count(*) FROM item_definitions')
        definition = await db.fetchval('''INSERT INTO item_definitions
            (code,name,category,rarity,start_price) VALUES ($1,'취소 검증 붕어','FISH','COMMON',100)
            RETURNING id''', f'cancel_qa_{number}')
        identities = []
        for _ in range(size):
            item_id = await db.fetchval('''INSERT INTO inventory_items
                (item_definition_id,owner_id,origin,acquired_at)
                VALUES ($1,$2,'ADMIN_GRANT',$3) RETURNING id''', definition, seller, datetime.now(timezone.utc))
            response = await member.post('/v1/listings', json={'inventory_item_id': item_id}, headers=bearer(member))
            assert response.status_code == 201, response.text
            identities.append(int(response.json()['id']))
        return identities

    await db.execute("SELECT setval(pg_get_serial_sequence('listings','id'), 100)")
    current, queued, following = await group(3)
    before = await snapshot()
    for client, expected in [(guest, 303), (member, 403)]:
        assert (await cancel(current, client=client)).status_code == expected
    for origin in ['https://untrusted.example', 'null', '']:
        response = await admin.post(f'/admin/listings/{current}/cancel', headers={'Origin': origin})
        assert response.status_code == 403
    request = admin.build_request('POST', f'/admin/listings/{current}/cancel')
    del request.headers['origin']
    assert (await admin.send(request)).status_code == 403
    for identity in [0, -1, 9223372036854775808]:
        assert (await cancel(identity)).status_code == 422
    assert (await cancel(999999)).status_code == 404
    for identity in [1, 24, 25]:
        assert (await cancel(identity)).status_code == 409
    assert before == await snapshot()
    print('PASS cancel: cookie permissions, Origin, ID validation and terminal states', flush=True)

    # 경매 소유자의 공개 HTTP API도 실제 인증으로 확인한다.
    response = await member.post(f'/v1/listings/management/{queued}/cancel',
                                 headers=bearer(member))
    assert response.status_code == 403
    assert (await admin.post(f'/v1/listings/management/{queued}/cancel')).status_code == 401
    response = await admin.post(f'/v1/listings/management/{queued}/cancel',
                                headers=bearer(admin))
    assert response.status_code == 200, response.text
    assert (await state(queued))['admin_cancelled_by'] == admin_id
    assert (await state(current))['status'] == 'BIDDING' and (await state(following))['status'] == 'QUEUED'
    print('PASS cancel: Auction Bearer API and queued cancellation preserve current listing', flush=True)

    response = await admin.post(f'/v1/listings/{current}/bids', json={'amount': 150}, headers=bearer(admin))
    assert response.status_code == 200, response.text
    wallet_before = (await admin.get('/v1/wallets/me', headers=bearer(admin))).json()
    response = await cancel(current)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    row = await state(current)
    assert row['status'] == 'CANCELLED' and row['admin_cancelled_by'] == admin_id
    assert row['admin_cancel_reason'] is None and row['closed_at'] is not None
    item = await db.fetchrow('SELECT * FROM inventory_items WHERE id=$1', row['inventory_item_id'])
    assert item['status'] == 'OWNED' and item['owner_id'] == seller
    assert (await state(following))['status'] == 'BIDDING'
    wallet_after = (await admin.get('/v1/wallets/me', headers=bearer(admin))).json()
    assert wallet_before['balance'] == wallet_after['balance']
    assert int(wallet_before['held_amount']) - int(wallet_after['held_amount']) == 150
    history = await db.fetch('SELECT * FROM item_events WHERE listing_id=$1 AND event_type=\'UNLISTED\'', current)
    assert len(history) == 1 and history[0]['actor_id'] == seller  # V1은 인벤토리 이력에 판매자를 기록한다.
    assert (await cancel(current)).status_code == 409
    assert (await state(current)) == row
    detail = await admin.get(f'/admin/auctions/{current}')
    assert '취소 관리자' in detail.text and 'auction-cancel-form' not in detail.text
    public = (await member.get(f'/v1/listings/{current}')).json()
    assert 'admin_cancel_reason' not in public and 'admin_cancelled_by' not in public
    before = await snapshot()
    await run_migration(env)
    assert before == await snapshot()
    print('PASS cancel: audit, inventory return, next listing, held release, no refund and safe replay', flush=True)

    duplicate, next_one, last = await group(3)
    results = await asyncio.gather(cancel(duplicate), cancel(duplicate))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (await state(next_one))['status'] == 'BIDDING' and (await state(last))['status'] == 'QUEUED'
    assert await db.fetchval("SELECT count(*) FROM item_events WHERE listing_id=$1 AND event_type='UNLISTED'", duplicate) == 1
    print('PASS cancel: simultaneous requests commit once and open only FIFO successor', flush=True)

    broken, successor = await group(2)
    before = await snapshot()
    # 다음 매물 저장 직전에 실패시켜 이미 처리한 재고 반환과 취소 기록도 rollback되는지 확인한다.
    await db.execute(f'''CREATE FUNCTION qa_fail_next() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.id = {successor} AND NEW.status = 'BIDDING' THEN
            RAISE EXCEPTION 'QA forced next listing failure'; END IF; RETURN NEW; END $$;
        CREATE TRIGGER qa_fail_next BEFORE UPDATE ON listings FOR EACH ROW EXECUTE FUNCTION qa_fail_next();''')
    try:
        assert (await cancel(broken)).status_code == 500
        assert before == await snapshot()
    finally:
        await db.execute('DROP TRIGGER qa_fail_next ON listings; DROP FUNCTION qa_fail_next()')
    assert (await cancel(broken)).status_code == 200
    print('PASS cancel: inventory/audit/queue rollback on late failure and successful retry', flush=True)

    ui_listing, ui_next = await group(2)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={'width': 1280, 'height': 1000})
        await context.add_cookies([{'name': c.name, 'value': c.value, 'url': base} for c in admin.cookies.jar])
        page = await context.new_page()
        errors, documents, posts = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda r: documents.append(r.url) if r.resource_type == 'document' else None)
        page.on('request', lambda r: posts.append(r) if r.method == 'POST' and r.url.endswith('/cancel') else None)
        await page.goto(base + f'/admin/auctions/{ui_listing}?status=BIDDING&page=1')
        await page.evaluate('window.qaShell = document.querySelector("header")')
        await expect(page.locator('[name="reason"]')).to_have_count(0)
        button = page.get_by_role('button', name='강제 취소', exact=True)
        await expect(button).to_be_enabled()
        await page.evaluate('window.scrollTo(0, 0)')
        await page.screenshot(path=str(ROOT / '.private/admin-auction-qa/cancel-desktop.png'), full_page=True)
        page.once('dialog', lambda d: d.dismiss())
        await button.click()
        assert not posts and (await state(ui_listing))['status'] == 'BIDDING'

        async def delay_cancel(route):
            await asyncio.sleep(0.3)
            await route.continue_()
        await page.route('**/admin/listings/*/cancel', delay_cancel)
        page.once('dialog', lambda d: d.accept())
        await button.click()
        await expect(button).to_be_disabled()
        await page.locator('#auction-cancel-form').evaluate('form => form.requestSubmit()')
        await expect(page.locator('h3').first).to_contain_text('취소')
        await expect(page.locator('#auction-cancel-form')).to_have_count(0)
        await expect(page.locator('dt').filter(has_text='취소 관리자')).to_have_count(1)
        assert len(posts) == 1 and posts[0].post_data is None and len(documents) == 1 and not errors
        assert await page.evaluate('qaShell === document.querySelector("header")')
        await page.set_viewport_size({'width': 390, 'height': 844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.screenshot(path=str(ROOT / '.private/admin-auction-qa/cancel-mobile.png'), full_page=True)
        await page.goto(base + f'/admin/auctions/{current}')
        await expect(page.locator('dt').filter(has_text='취소 관리자')).to_have_count(1)

        # 서버에서 이미 종료된 매물의 오래된 화면은 409를 표시하고 자동 재전송하지 않는다.
        await page.goto(base + f'/admin/auctions/{ui_next}')
        assert (await cancel(ui_next)).status_code == 200
        page.once('dialog', lambda d: d.accept())
        await page.get_by_role('button', name='강제 취소', exact=True).click()
        await expect(page.locator('#admin-message')).to_contain_text('대기 또는 진행 중인 매물만')
        await expect(page.get_by_role('button', name='강제 취소', exact=True)).to_be_enabled()
        # 서버가 성공한 뒤 응답만 유실되면 POST를 재전송하지 않고 재조회로 상태를 복구한다.
        lost_response, = await group()
        await page.goto(base + f'/admin/auctions/{lost_response}')
        await page.unroute('**/admin/listings/*/cancel', delay_cancel)
        async def lose_response(route):
            response = await route.fetch()
            assert response.status == 200
            await route.abort('failed')
        await page.route('**/admin/listings/*/cancel', lose_response)
        previous_posts = len(posts)
        page.once('dialog', lambda d: d.accept())
        await page.get_by_role('button', name='강제 취소', exact=True).click()
        await expect(page.locator('#admin-message')).to_contain_text('처리 결과를 확인')
        assert len(posts) == previous_posts + 1 and (await state(lost_response))['status'] == 'CANCELLED'
        await page.reload()
        await expect(page.locator('#auction-cancel-form')).to_have_count(0)
        await expect(page.locator('dt').filter(has_text='취소 관리자')).to_have_count(1)
        assert not errors
        await browser.close()
    print('PASS browser cancel: confirmation, no request body, duplicate prevention, shell, audit and stale-state error', flush=True)
