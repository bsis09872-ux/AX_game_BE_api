"""임시 QA 서버에서 도메인 이동 후 회원/아이템 관리의 기존 계약을 검증한다."""

from datetime import datetime, timedelta, timezone
import secrets

import httpx
from playwright.async_api import async_playwright, expect


async def verify_admin_domains(base, guest, member, admin, seller):
    pages = [
        '/admin', '/admin/catalogs', '/admin/catalogs/new', '/admin/history',
        '/admin/members', '/admin/members/new', f'/admin/members/{seller}',
        f'/admin/members/{seller}/inventory',
    ]
    for path in pages + ['/admin/item-catalogs', '/admin/item-images']:
        for client, expected in [(guest, 303), (member, 403), (admin, 200)]:
            response = await client.get(path)
            assert response.status_code == expected, (path, response.status_code)
            if expected == 200:
                assert response.headers['cache-control'] == 'no-store'

    catalog = dict(code='boundary_qa', name='=검증 붕어', category='FISH', rarity='COMMON', start_price=100)
    assert (await member.post('/admin/item-catalogs', json=catalog)).status_code == 403
    assert (await admin.post('/admin/item-catalogs', json=catalog, headers={'Origin': 'null'})).status_code == 403
    response = await admin.post('/admin/item-catalogs', json=catalog)
    assert response.status_code == 201, response.text
    definition = response.json()['id']
    assert (await admin.get(f'/admin/catalogs/{definition}/edit')).status_code == 200
    response = await admin.patch(f'/admin/item-catalogs/{definition}', json={'description': '수정됨', 'start_price': 120})
    assert response.status_code == 200 and response.json()['start_price'] == 120
    response = await admin.get('/admin/item-catalogs', params={'category': 'FISH', 'rarity': 'COMMON'})
    assert any(row['id'] == definition and row['description'] == '수정됨' for row in response.json()['items'])
    response = await admin.get('/admin/item-catalogs/export.csv')
    assert response.status_code == 200 and "'=검증 붕어" in response.text
    assert (await admin.delete(f'/admin/item-catalogs/{definition}')).status_code == 204
    assert (await admin.get(f'/admin/catalogs/{definition}/edit')).status_code == 404
    assert (await admin.post('/admin/auctions/1/cancel')).status_code == 404
    print('PASS domains: existing pages, catalog CRUD/filter/export, permissions and obsolete endpoint removal', flush=True)

    password = secrets.token_urlsafe(24)
    account = dict(login_id='qa_created_member', display_name='관리자가 만든 회원', password=password)
    assert (await member.post('/admin/member-accounts', json=account)).status_code == 403
    assert (await admin.post('/admin/member-accounts', json=account, headers={'Origin': 'null'})).status_code == 403
    response = await admin.post('/admin/member-accounts', json=account)
    assert response.status_code == 201, response.text
    identity = response.json()['id']
    async with httpx.AsyncClient(base_url=base, headers={'Origin': base}) as created:
        async def login():
            return await created.post('/login', data={'login_id': account['login_id'], 'password': password})

        assert (await login()).status_code == 303
        assert (await created.get('/admin')).status_code == 403
        response = await admin.patch(f'/admin/member-accounts/{identity}/role', json={'role': 'ADMIN'})
        assert response.status_code == 200 and response.json()['role'] == 'ADMIN'
        assert (await created.get('/admin')).status_code == 200
        response = await admin.patch(f'/admin/member-accounts/{identity}/role', json={'role': 'USER'})
        assert response.status_code == 200
        assert (await created.get('/admin')).status_code == 403

        until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        response = await admin.patch(f'/admin/member-accounts/{identity}/bid-restriction', json={'until': until})
        assert response.status_code == 200 and response.json()['manual_auction_blocked_until']
        response = await admin.patch(f'/admin/member-accounts/{identity}/bid-restriction', json={'until': None})
        assert response.status_code == 200 and response.json()['manual_auction_blocked_until'] is None

        old_access = created.cookies.get('access_token')
        response = await admin.patch(f'/admin/member-accounts/{identity}/login-suspension', json={'suspended': True})
        assert response.status_code == 200 and response.json()['login_suspended_at']
        assert (await created.get('/v1/users/me', headers={'Authorization': 'Bearer ' + old_access})).status_code == 401
        response = await admin.patch(f'/admin/member-accounts/{identity}/login-suspension', json={'suspended': False})
        assert response.status_code == 200 and response.json()['login_suspended_at'] is None
        # 정지를 풀어도 이전 로그인 세션은 복구되지 않는다.
        assert (await created.get('/v1/users/me', headers={'Authorization': 'Bearer ' + old_access})).status_code == 401
        assert (await login()).status_code == 303
        assert (await created.get('/v1/users/me', headers={
            'Authorization': 'Bearer ' + created.cookies.get('access_token'),
        })).status_code == 200
    print('PASS domains: member creation, role, bid restriction, suspension and session revocation', flush=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context()
        await context.add_cookies([{'name': c.name, 'value': c.value, 'url': base} for c in admin.cookies.jar])
        page = await context.new_page()
        errors, documents = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda r: documents.append(r.url) if r.resource_type == 'document' else None)
        await page.goto(base + '/admin')
        await page.evaluate('window.qaHeader = document.querySelector("header")')
        for tab, url in [('catalogs', '/admin/catalogs'), ('members', '/admin/members'),
                         ('auctions', '/admin/auctions'), ('trades', '/admin/auction-trades'),
                         ('home', '/admin')]:
            await page.locator(f'[data-admin-tab="{tab}"]').click()
            await expect(page).to_have_url(base + url)
            await expect(page.locator(f'[data-admin-tab="{tab}"]')).to_have_attribute('aria-current', 'page')
        assert await page.evaluate('qaHeader === document.querySelector("header")')
        assert len(documents) == 1 and not errors
        await browser.close()
    print('PASS domains: navigation across owning domains preserves the shared header and tabs', flush=True)
