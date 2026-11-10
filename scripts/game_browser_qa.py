"""두 프로세스와 두 계정으로 새 화면의 실제 브라우저 동작을 확인한다."""

import asyncio

from playwright.async_api import async_playwright, expect


async def check_browser(bases, clients, db, restart, artifacts):
    # 이 함수에 전달되는 db는 검증 스크립트가 생성한 임시 DB다.
    await db.execute('DELETE FROM world_presences')
    await db.execute('DELETE FROM fishing_cooldowns')
    errors, failed_assets = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        pages, sockets = [], [[], []]
        try:
            for index, client in enumerate(clients):
                context = await browser.new_context(viewport={'width': 1280, 'height': 900})
                await context.add_cookies([
                    {'name': key, 'value': value, 'url': bases[index]} for key, value in client.cookies.items()
                ])
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda response: failed_assets.append(response.url)
                        if '/static/' in response.url and response.status >= 400 else None)
                page.on('websocket', lambda ws, index=index: sockets[index].append(ws))
                pages.append(page)
                await page.goto(bases[index] + '/me')
                if index == 0:
                    # 화면과 WS가 동시에 갱신해도 회전식 refresh 토큰을 재사용하지 않는다.
                    refreshes = []
                    page.on('request', lambda request: refreshes.append(request.url)
                            if request.url.endswith('/session/refresh') else None)
                    await context.add_cookies([
                        {'name': 'access_token', 'value': 'expired-qa-token', 'url': bases[index]}
                    ])
                    refreshed = await page.evaluate('''async () => {
                        const {ensureSession} = await import('/static/auth-session.js');
                        return Promise.all(Array.from({length: 3}, () =>
                            ensureSession(new AbortController().signal)));
                    }''')
                    assert all(result and result['expires_in'] > 30 for result in refreshed)
                    assert len(refreshes) == 1, refreshes
                    print('PASS session: concurrent refresh recovers once using HttpOnly cookies', flush=True)
                await page.evaluate("window.qaShell = document.querySelector('.topbar')")
                await page.locator('.topbar a[href="/v1/play"]').evaluate("el => el.setAttribute('href', '/v1/play?debug=1')")
                await page.locator('.topbar a[href="/v1/play?debug=1"]').click()
                await page.wait_for_function('window.fa?.network.connected', timeout=25000)
                assert await page.evaluate("window.qaShell === document.querySelector('.topbar')")
                await expect(page.locator('#stage canvas')).to_have_count(1)
            a, b = pages
            for page in pages:
                await expect(page.locator('#names > div')).to_have_count(1, timeout=10000)

            await b.locator('#skin-btn').click()
            await b.locator('[data-skin="ghost"]').click()
            await a.wait_for_function("[...fa.network.others.values()].some(p => p.skin === 'ghost')")
            before = await a.evaluate('[...fa.network.others.values()][0].y')
            await b.keyboard.press('ArrowDown', delay=350)
            await a.wait_for_function(f'[...fa.network.others.values()][0].y > {before + 5}')

            # 동일 메뉴는 새 캔버스/소켓을 만들지 않는다.
            await a.evaluate("window.qaCanvas = document.querySelector('#stage canvas')")
            count = len(sockets[0])
            for _ in range(20):
                await a.locator('.topbar a[aria-current="page"]').evaluate("el => el.href = location.href")
                await a.locator('.topbar a[aria-current="page"]').click()
            assert len(sockets[0]) == count
            assert await a.evaluate("window.qaCanvas === document.querySelector('#stage canvas')")
            print('PASS browser: two accounts/processes, movement, skins, shared shell, repeated menu', flush=True)

            await a.keyboard.press('ArrowDown', delay=1100)
            await a.wait_for_function('fa.PLAYER.y >= 140')
            await a.wait_for_timeout(300)
            before_items = await db.fetchval('SELECT count(*) FROM inventory_items')
            captured = {}

            async def lose_result(route):
                await route.fetch()
                captured['cast'] = route.request.post_data_json['cast_id']
                await route.abort()

            await a.route('**/v1/play/fishing-results', lose_result, times=1)
            await a.keyboard.press('Space')
            await a.keyboard.press('Space')
            await a.wait_for_function("fa.fishing.state === 'bite'", timeout=10000)
            await a.keyboard.press('Space')
            await a.wait_for_function("fa.fishing.state === 'uncertain'", timeout=10000)
            assert await db.fetchval('SELECT count(*) FROM inventory_items') == before_items + 1
            await a.keyboard.press('ArrowRight', delay=100)
            assert await a.evaluate('fa.fishing.castId') == captured['cast']
            await a.keyboard.press('Space')
            await expect(a.locator('#catch')).to_be_visible(timeout=10000)
            assert await db.fetchval('SELECT count(*) FROM inventory_items') == before_items + 1
            print('PASS browser: verified cast, bite, lost-response recovery without duplicate reward', flush=True)

            for path in ['/auctions', '/inventory']:
                await a.locator(f'.hudbar [data-open="{path}"]').click()
                await expect(a.locator('#overlay')).to_be_visible()
                await expect(a.frame_locator('#ov-frame').locator('main')).to_be_visible()
                await a.locator('#ov-close').click()
                await expect(a.locator('#overlay')).to_be_hidden()
            await a.screenshot(path=str(artifacts / 'integrated-desktop.png'), full_page=True)

            # 전환 준비가 실패해도 이전 본문이 남고 임시 게임/소켓은 정리된다.
            await a.locator('.topbar a[href="/inventory"]').click()
            await expect(a.locator('#stage canvas')).to_have_count(0)
            socket_count = len(sockets[0])
            await a.route('**/static/maps/world.tmj', lambda route: route.abort())
            await a.locator('.topbar a[href="/v1/play"]').click()
            await a.wait_for_timeout(1200)
            assert '/inventory' in a.url
            assert len(sockets[0]) == socket_count
            await expect(a.locator('[data-page-preparation]')).to_have_count(0)
            await a.unroute('**/static/maps/world.tmj')
            await a.locator('.topbar a[href="/v1/play"]').click()
            await expect(a.locator('#net')).to_have_text('2명 접속', timeout=15000)
            print('PASS navigation: failed preparation preserves previous page, cleanup and retry', flush=True)

            # 기존 연결이 끊겨도 같은 DB의 다른 프로세스와 다시 공유한다.
            await restart(1)
            await expect(b.locator('#net')).to_have_text('2명 접속', timeout=15000)
            await expect(a.locator('#names > div')).to_have_count(1)
            await a.set_viewport_size({'width': 390, 'height': 844})
            assert await a.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await a.screenshot(path=str(artifacts / 'integrated-mobile.png'), full_page=True)

            # 다른 맵은 같은 방 목록에 섞이지 않는다.
            await b.goto(bases[1] + '/v1/play?map=lake&debug=1')
            await b.wait_for_function('window.fa?.network.connected')
            await expect(a.locator('#names > div')).to_have_count(0)
            await expect(b.locator('#names > div')).to_have_count(0)
            await b.goto(bases[1] + '/v1/play?map=halloween&debug=1')
            await b.wait_for_function('window.fa?.network.connected')

            await b.evaluate("fetch('/logout', {method:'POST', credentials:'same-origin'})")
            await expect(b).to_have_url(__import__('re').compile('/login'), timeout=15000)
            assert not errors, errors
            assert not failed_assets, failed_assets
            print('PASS browser: embedded auction/inventory, restart, room isolation, mobile, logout', flush=True)
        finally:
            if errors:
                print('Browser errors:', errors, flush=True)
            for index, page in enumerate(pages):
                await page.screenshot(path=str(artifacts / f'last-page-{index}.png'), full_page=True)
            await browser.close()
