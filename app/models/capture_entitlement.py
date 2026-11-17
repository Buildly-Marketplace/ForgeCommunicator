"""
Paid access to the Capture app's server features (saving ideas, AI estimates, sending to Labs).

One row per (user, source). A user has access if any row is active and unexpired:
- source="revenuecat": App Store / Google Play purchase, mirrored from RevenueCat.
  Subscriptions carry expires_at; one-time ("lifetime") purchases have expires_at = NULL.
- source="grant": comped by a platform admin (optionally time-limited).

RevenueCat rows are always recomputed from RevenueCat's API — never from what the
mobile client claims — so they can't be forged by a modified app.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin


class CaptureEntitlement(Base, TimestampMixin):
    __tablename__ = "capture_entitlements"
    __table_args__ = (UniqueConstraint("user_id", "source", name="uq_capture_entitlement_user_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "revenuecat" | "grant"

    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lifetime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    will_renew: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    product_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    store: Mapped[str | None] = mapped_column(String(30), nullable=True)  # app_store | play_store | ...
    management_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)  # for grants: why / who
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # last RevenueCat entitlement payload

    user = relationship("User")

    def is_current(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.active and (self.expires_at is None or self.expires_at > now)
