from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


async def upgrade_member_controls(connection: AsyncConnection) -> None:
    """기존 회원 데이터를 유지하는 추가형 스키마 변경. 재실행해도 안전하다."""
    columns = await connection.run_sync(lambda sync: {c['name'] for c in inspect(sync).get_columns('users')})
    for name in ('login_suspended_at', 'manual_auction_blocked_until'):
        if name not in columns:
            await connection.execute(text(f'ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} TIMESTAMPTZ NULL'))
