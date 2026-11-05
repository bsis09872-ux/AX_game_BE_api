# 회원가입 저장, 로그인 토큰 발급, 인증 확인과 토큰 폐기를 조율한다.
from auth.application.contracts import (
    CreatedUser, IssuedToken, PasswordHasher, RevokedTokenRepository,
    TokenClaims, TokenCodec, Transaction, UserCreator, UserReader,
)
from auth.domain.exceptions import InvalidCredentialsError, InvalidTokenError


class AuthService:
    def __init__(
        self, password_hasher: PasswordHasher, user_creator: UserCreator,
        user_reader: UserReader, token_codec: TokenCodec,
        revoked_tokens: RevokedTokenRepository, transaction: Transaction,
    ):
        self.password_hasher = password_hasher
        self.user_creator = user_creator
        self.user_reader = user_reader
        self.token_codec = token_codec
        self.revoked_tokens = revoked_tokens
        self.transaction = transaction

    async def register_user(
        self, login_id: str, display_name: str, password: str
    ) -> CreatedUser:
        password_hash = await self.password_hasher.hash(password)
        user = await self.user_creator.create_user(
            login_id=login_id, display_name=display_name, password_hash=password_hash
        )
        # 응답 전 저장을 확정한다. 실패 시 요청 세션의 get_db가 rollback한다.
        await self.transaction.commit()
        return user

    async def login(self, login_id: str, password: str) -> IssuedToken:
        if not 4 <= len(login_id) <= 50 or not 1 <= len(password) <= 1024:
            raise InvalidCredentialsError()
        user = await self.user_reader.find_by_login_id(login_id)
        if user is None:
            # 없는 계정도 해싱 비용을 거쳐 즉시 실패 응답으로 계정 유무를 드러내지 않는다.
            await self.password_hasher.hash(password)
            raise InvalidCredentialsError()
        matches = await self.password_hasher.verify(password, user.password_hash)
        if not matches or not user.is_active:
            raise InvalidCredentialsError()
        return self.token_codec.issue(user.id)

    async def authenticate(self, token: str) -> TokenClaims:
        claims = self.token_codec.decode(token)
        if await self.revoked_tokens.contains(claims.jti):
            raise InvalidTokenError()
        user = await self.user_reader.find_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return claims

    async def logout(self, token: str) -> None:
        # 서명과 만료는 검증하되 이미 폐기한 토큰도 재시도할 수 있다.
        claims = self.token_codec.decode(token)
        user = await self.user_reader.find_by_id(claims.user_id)
        if user is None:
            raise InvalidTokenError()
        await self.revoked_tokens.revoke(claims)
        await self.transaction.commit()
