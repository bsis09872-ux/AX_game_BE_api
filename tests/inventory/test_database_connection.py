"""팀 공통 database.py의 DB 연결 테스트 (진짜 PostgreSQL이 필요하다)

환경 변수 DATABASE_URL이 있거나 프로젝트 루트의 .env에 있으면 돈다. 없으면 건너뛴다.
database.py는 import하는 순간 DATABASE_URL로 엔진을 만들어서(없으면 KeyError),
환경 변수가 없는 곳에서는 import하지 않도록 테스트 안에서 import한다.
"""

import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

# database.py가 하는 것과 같이 프로젝트 루트의 .env를 읽는다 (파일이 없으면 아무 일도 안 한다)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL이 없어 DB 연결 테스트를 건너뛴다")
class DatabaseConnectionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import database

        self.database = database
        # 테스트마다 이벤트 루프가 달라서 남은 연결을 닫고 새로 시작한다
        await database.engine.dispose()

    async def asyncTearDown(self):
        await self.database.engine.dispose()

    async def test_select_1_works_through_get_db(self):
        async for session in self.database.get_db():
            result = await session.execute(text("SELECT 1"))
            self.assertEqual(result.scalar_one(), 1)

    async def test_server_is_postgresql(self):
        async for session in self.database.get_db():
            result = await session.execute(text("SELECT version()"))
            self.assertTrue(result.scalar_one().startswith("PostgreSQL"))


if __name__ == "__main__":
    unittest.main()
