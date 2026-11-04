"""응답 모델 테스트 (by claude)"""

import json
import unittest

from pydantic import BaseModel

from common_study.responses import IdStr, PageParams, PageResponse


class 아이템(BaseModel):
    """테스트용 응답 스키마. 실제 도메인 스키마도 ID 필드를 이렇게 쓴다."""

    id: IdStr
    owner_id: IdStr | None = None
    start_price: int


class ID문자열_테스트(unittest.TestCase):
    def test_JSON으로_내보낼_때_ID는_문자열이다(self):
        본문 = 아이템(id=17, start_price=100).model_dump(mode="json")
        self.assertEqual(본문["id"], "17")

    def test_파이썬_안에서는_ID가_int_그대로이다(self):
        객체 = 아이템(id=17, start_price=100)
        self.assertEqual(객체.id, 17)
        self.assertEqual(객체.model_dump()["id"], 17)

    def test_JSON_글자로_만들어도_ID는_문자열이다(self):
        글 = 아이템(id=17, start_price=100).model_dump_json()
        self.assertEqual(json.loads(글)["id"], "17")

    def test_값이_없으면_문자열_null이_아니라_JSON_null이다(self):
        글 = 아이템(id=1, start_price=100).model_dump_json()
        self.assertIsNone(json.loads(글)["owner_id"])
        self.assertNotIn('"null"', 글)

    def test_값이_있는_선택_ID도_문자열이다(self):
        본문 = 아이템(id=1, owner_id=7, start_price=100).model_dump(mode="json")
        self.assertEqual(본문["owner_id"], "7")

    def test_금액은_숫자_그대로이다(self):
        본문 = 아이템(id=1, start_price=100).model_dump(mode="json")
        self.assertEqual(본문["start_price"], 100)
        self.assertIsInstance(본문["start_price"], int)


class 목록응답_테스트(unittest.TestCase):
    def test_items_page_size_total_모양이다(self):
        응답 = PageResponse[아이템](
            items=[아이템(id=17, start_price=100)], page=1, size=20, total=1
        )
        본문 = 응답.model_dump(mode="json")
        self.assertEqual(set(본문), {"items", "page", "size", "total"})
        self.assertEqual(본문["page"], 1)
        self.assertEqual(본문["size"], 20)
        self.assertEqual(본문["total"], 1)

    def test_목록_안_항목의_ID도_문자열이다(self):
        응답 = PageResponse[아이템](
            items=[아이템(id=17, start_price=100), 아이템(id=18, start_price=200)],
            page=1,
            size=20,
            total=2,
        )
        본문 = 응답.model_dump(mode="json")
        self.assertEqual([항목["id"] for 항목 in 본문["items"]], ["17", "18"])

    def test_빈_목록도_만들_수_있다(self):
        본문 = PageResponse[아이템](items=[], page=1, size=20, total=0).model_dump(mode="json")
        self.assertEqual(본문["items"], [])
        self.assertEqual(본문["total"], 0)


class 페이지파라미터_테스트(unittest.TestCase):
    # PageParams()를 값 없이 만들면 기본값이 Query 객체라서, 값을 직접 넘겨서 만든다
    def test_넘긴_값을_그대로_가진다(self):
        파라미터 = PageParams(page=2, size=10)
        self.assertEqual(파라미터.page, 2)
        self.assertEqual(파라미터.size, 10)

    def test_offset은_앞_페이지_항목_수이다(self):
        기대 = [(1, 20, 0), (2, 20, 20), (3, 10, 20), (2, 50, 50)]
        for 페이지, 크기, offset in 기대:
            with self.subTest(페이지=페이지, 크기=크기):
                self.assertEqual(PageParams(page=페이지, size=크기).offset, offset)


if __name__ == "__main__":
    unittest.main()