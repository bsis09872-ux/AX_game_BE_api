"""기존 listings 테이블에 관리자 취소 기록 컬럼만 추가한다.

uv run --frozen python scripts/migrate-auction-admin-cancel.py
대상은 DATABASE_URL / .env.local / .env 순서로 선택한다. 행이나 기존 컬럼은 삭제하지 않는다.
"""

import asyncio
from pathlib import Path
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from database import engine


async def migrate():
    try:
        async with engine.begin() as connection:
            # 사용 중인 테이블을 오래 기다리지 않고 실패하면 전체 변경을 rollback한다.
            await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            columns = await connection.run_sync(
                lambda sync: {c['name']: c for c in inspect(sync).get_columns('listings')}
            )
            expected = {'admin_cancelled_by': 'BIGINT'}
            added = []
            for name, sql_type in expected.items():
                if name in columns:
                    if str(columns[name]['type']) != sql_type or not columns[name]['nullable']:
                        raise RuntimeError(f'{name}의 기존 타입/NULL 허용 여부를 확인하세요.')
                    continue
                await connection.execute(text(
                    f'ALTER TABLE listings ADD COLUMN IF NOT EXISTS {name} {sql_type} NULL'
                ))
                added.append(name)
        print('추가한 컬럼: ' + ', '.join(added) if added else '이미 적용됨: 기존 컬럼과 데이터를 유지합니다.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(migrate())
