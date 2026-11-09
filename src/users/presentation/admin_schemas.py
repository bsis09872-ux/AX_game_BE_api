from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, AwareDatetime
from users.domain.user import User


class AdminMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    login_id: str = Field(min_length=4, max_length=50, pattern='^[a-z0-9_]+$')
    display_name: str = Field(min_length=2, max_length=50, pattern=r'\S')
    password: str = Field(min_length=1, max_length=1024, repr=False)


class AdminMemberRoleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['USER', 'ADMIN']


class AdminLoginSuspensionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    suspended: StrictBool


class AdminBidRestrictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    until: AwareDatetime | None


class AdminMemberResponse(BaseModel):
    id: str
    login_id: str
    display_name: str
    role: Literal['USER', 'ADMIN']
    is_active: bool
    login_suspended_at: datetime | None
    created_at: datetime
    auction_purchase_count: int
    auction_blocked_until: datetime | None
    manual_auction_blocked_until: datetime | None
    effective_auction_blocked_until: datetime | None

    @classmethod
    def from_user(cls, user: User):
        return cls(id=str(user.id), login_id=user.login_id, display_name=user.display_name,
                   role=user.role, is_active=user.is_active(), login_suspended_at=user.login_suspended_at,
                   created_at=user.created_at,
                   auction_purchase_count=user.auction_purchase_count,
                   auction_blocked_until=user.auction_blocked_until,
                   manual_auction_blocked_until=user.manual_auction_blocked_until,
                   effective_auction_blocked_until=user.effective_auction_blocked_until)
