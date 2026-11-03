"""공통 예외 테스트 (by claude)"""

import unittest
from common_item.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    RuleError,
    UnauthorizedError,
    ValidationFailedError,
    ServiceUnavailableError
)

class 공통예외_테스트(unittest.TestCase):
    def test_자식_예외는_상태코드와_코드가_명세와_같다(self):
        기대 = [
            (RuleError, 400, "RULE_VIOLATION"),
            (UnauthorizedError, 401, "UNAUTHORIZED"),
            (ForbiddenError, 403, "FORBIDDEN"),
            (NotFoundError, 404, "NOT_FOUND"),
            (ValidationFailedError, 422, "VALIDATION_ERROR"),
            (RateLimitedError, 429, "RATE_LIMITED"),
            (ServiceUnavailableError, 503, 'SERVICE_UNAVAILABLE')
        ]
        for 예외, 상태, 코드 in 기대:
            with self.subTest(코드=코드):
                self.assertEqual(예외.status_code, 상태)
                self.assertEqual(예외.code, 코드)
                self.assertIsInstance(예외(), AppError)

    def test_부모를_그대로_던지면_500_서버_오류이다(self):
        오류 = AppError()
        self.assertEqual(오류.status_code, 500)
        self.assertEqual(오류.code, "INTERNAL_ERROR")

    def test_본문은_detail_안에_code와_message가_있다(self):
        본문 = ForbiddenError().to_body()
        self.assertEqual(set(본문), {"detail"})
        self.assertEqual(
            본문["detail"],
            {"code": "FORBIDDEN", "message": "이 기능을 사용할 권한이 없습니다."},
        )

    def test_params가_없으면_본문에서_뺀다(self):
        self.assertNotIn("params", NotFoundError().to_body()["detail"])
        self.assertNotIn("params", NotFoundError(params={}).to_body()["detail"])

    def test_params가_있으면_detail_안에_들어간다(self):
        오류 = RateLimitedError(params={"retry_after_seconds": 6})
        self.assertEqual(오류.to_body()["detail"]["params"], {"retry_after_seconds": 6})

    def test_도메인은_클래스_속성만_바꿔_자기_예외를_만든다(self):
        class 아이템없음(NotFoundError):
            code = "ITEM_NOT_FOUND"
            message = "아이템을 찾을 수 없습니다."

        오류 = 아이템없음()
        self.assertEqual(오류.status_code, 404)
        self.assertEqual(오류.to_body()["detail"]["code"], "ITEM_NOT_FOUND")

    def test_만들_때_메시지와_코드를_바꿀_수_있다(self):
        오류 = RuleError("이미 경매 중입니다.", code="ITEM_STATE_CONFLICT")
        본문 = 오류.to_body()["detail"]
        self.assertEqual(본문["code"], "ITEM_STATE_CONFLICT")
        self.assertEqual(본문["message"], "이미 경매 중입니다.")
        self.assertEqual(str(오류), "이미 경매 중입니다.")

    def test_한_예외에서_바꾼_값이_다른_예외에_번지지_않는다(self):
        RuleError("첫째", code="A")
        둘째 = RuleError()
        self.assertEqual(둘째.code, "RULE_VIOLATION")
        self.assertEqual(RuleError.code, "RULE_VIOLATION")


if __name__ == "__main__":
    unittest.main()