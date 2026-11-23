"""Arama kotası: aboneliği olmayan kullanıcılar ayda belirli sayıda ücretsiz arama yapabilir.

Sayım search_logs tablosundan yapılır (olay metni orada saklanmaz). Ay, ayarlardaki
saat dilimine (varsayılan Europe/Istanbul) göre takvim ayıdır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import SearchLog, Subscription, SubscriptionStatus, User


@dataclass(frozen=True)
class QuotaStatus:
    unlimited: bool  # etkin aboneliği var
    used: int  # bu ay yapılan arama sayısı
    limit: int | None  # ücretsiz hak (abonede None)
    period_start: datetime

    @property
    def remaining(self) -> int | None:
        return None if self.unlimited else max(0, (self.limit or 0) - self.used)

    @property
    def allowed(self) -> bool:
        return self.unlimited or (self.remaining or 0) > 0


def month_start(now: datetime, tz_name: str) -> datetime:
    """`now` anının içinde bulunduğu takvim ayının başlangıcı (UTC olarak)."""
    local = now.astimezone(ZoneInfo(tz_name))
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def has_active_subscription(session: Session, user: User, now: datetime) -> bool:
    """Etkin abonelik ya da iptal edilmiş ama ödemesi yapılmış dönemi bitmemiş abonelik."""
    active = (Subscription.status == SubscriptionStatus.ACTIVE) & (
        Subscription.current_period_end.is_(None) | (Subscription.current_period_end > now)
    )
    canceled_but_paid = (Subscription.status == SubscriptionStatus.CANCELED) & (
        Subscription.current_period_end > now
    )
    stmt = select(Subscription.id).where(
        Subscription.user_id == user.id, active | canceled_but_paid
    )
    return session.execute(stmt.limit(1)).first() is not None


def get_quota(session: Session, user: User, now: datetime | None = None,
              settings: Settings | None = None) -> QuotaStatus:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    start = month_start(now, settings.quota_timezone)
    used = session.scalar(
        select(func.count(SearchLog.id)).where(
            SearchLog.user_id == user.id, SearchLog.created_at >= start
        )
    ) or 0
    if has_active_subscription(session, user, now):
        return QuotaStatus(unlimited=True, used=used, limit=None, period_start=start)
    return QuotaStatus(unlimited=False, used=used, limit=settings.free_searches_per_month,
                       period_start=start)
