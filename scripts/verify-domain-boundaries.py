"""함수 내부 import도 포함해 도메인 간 순환 참조와 관리자 라우트 소유권을 검증한다."""

import ast
from collections import Counter
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
DOMAINS = {'auth', 'users', 'auction', 'inventory', 'wallet'}


def main():
    graph = {name: set() for name in DOMAINS}
    for domain in sorted(DOMAINS):
        for path in (SRC / domain).rglob('*.py'):
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    imports = [node.module]
                elif isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                for name in imports:
                    target = name.split('.')[0]
                    if target in DOMAINS and target != domain:
                        graph[domain].add(target)
                    # 도메인과 애플리케이션 계층은 구현 기술을 가져오지 않는다.
                    if path.relative_to(SRC / domain).parts[0] in {'domain', 'application'}:
                        assert target not in {'fastapi', 'sqlalchemy', 'database'}, (path, name)
                        assert '.infrastructure' not in name and '.presentation' not in name, (path, name)

    def visit(name, ancestors):
        assert name not in ancestors, ' -> '.join([*ancestors, name])
        for target in graph[name]:
            visit(target, [*ancestors, name])

    for domain in DOMAINS:
        visit(domain, [])
    assert graph['auth'] <= {'users'}, graph
    assert not graph['users'], graph
    assert not (SRC / 'admin').exists()
    for path in (SRC / 'auth').rglob('*.py'):
        assert not path.name.startswith('admin'), path
    print('PASS domain imports: acyclic including function imports; Auth -> Users only', flush=True)

    env = {**os.environ, 'PYTHONPATH': str(SRC)}
    for first in ['auth.wiring', 'auction.wiring', 'inventory.wiring', 'users.wiring', 'composition']:
        code = f'import {first}; import main; print("PASS fresh import: {first}")'
        subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, check=True)

    sys.path.insert(0, str(SRC))
    from main import app

    def endpoints(router, prefix=''):
        for route in router.routes:
            # 현재 FastAPI는 include_router 등록을 지연하여 보관한다.
            if hasattr(route, 'original_router'):
                yield from endpoints(route.original_router, prefix + route.include_context.prefix)
            elif hasattr(route, 'methods'):
                for method in route.methods:
                    yield (prefix + route.path, method), route

    entries = list(endpoints(app))
    routes = dict(entries)
    counts = Counter(key for key, route in entries)
    assert all(count == 1 for count in counts.values()), counts
    ownership = {
        ('/admin', 'GET'): 'web_router',
        ('/admin/members', 'GET'): 'users',
        ('/admin/member-accounts', 'POST'): 'users',
        ('/admin/item-catalogs', 'POST'): 'inventory',
        ('/admin/members/{member_id}/inventory', 'GET'): 'inventory',
        ('/admin/auctions', 'GET'): 'auction',
        ('/admin/auction-trades', 'GET'): 'auction',
        ('/admin/listings/{listing_id}/cancel', 'POST'): 'auction',
    }
    for key, owner in ownership.items():
        assert routes[key].endpoint.__module__.split('.')[0] == owner, key
    assert ('/admin/auctions/{listing_id}/cancel', 'POST') not in routes
    for route in routes.values():
        if route.path.startswith('/admin'):
            assert not route.endpoint.__module__.startswith('auth.'), route.path
    schema = app.openapi()
    assert 'requestBody' not in schema['paths']['/admin/listings/{listing_id}/cancel']['post']
    assert 'requestBody' not in schema['paths']['/v1/listings/management/{listing_id}/cancel']['post']
    print('PASS route ownership, unique endpoints and PR35 bodyless cancellation contracts', flush=True)


if __name__ == '__main__':
    main()
