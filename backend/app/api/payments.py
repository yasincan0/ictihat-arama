"""Abonelik uç noktaları: ödeme formu başlatma, sağlayıcı dönüşü, webhook, iptal.

Akış:
1. POST /payments/checkout: fatura bilgileriyle sağlayıcıda ödeme formu açılır; jeton
   kullanıcıyla eşlenip saklanır (fatura bilgileri saklanmaz).
2. Kullanıcı formu doldurur; sağlayıcı tarayıcıyı POST /payments/callback adresine
   (form alanı: token) gönderir. Sonuç sağlayıcıdan SORGULANARAK alınır, gövdeye güvenilmez.
3. Yenilemelerde sağlayıcı POST /payments/webhook/iyzico çağırır; imza doğrulanır ve
   abonelik yine sağlayıcıdan sorgulanarak güncellenir.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_verified_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ratelimit import limit
from app.models import PaymentCheckout, Subscription, SubscriptionStatus, User
from app.schemas.auth import MessageResponse
from app.schemas.payments import (
    BillingRequest,
    CheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.services.payments import (
    BillingInfo,
    PaymentError,
    PaymentProvider,
    SubscriptionInfo,
    get_payment_provider,
)
from app.services.quota import has_active_subscription

logger = logging.getLogger(__name__)
def payments_enabled_guard() -> None:
    """Abonelik sistemi kapalıyken (PAYMENTS_ENABLED=false) tüm ödeme uçları 404 döner."""
    if not get_settings().payments_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Abonelik sistemi şu an kapalı")


router = APIRouter(prefix="/payments", tags=["abonelik"],
                   dependencies=[Depends(payments_enabled_guard)])

PLAN = "aylik"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def latest_subscription(db: Session, user: User) -> Subscription | None:
    return db.scalars(
        select(Subscription).where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
    ).first()


def sync_subscription(db: Session, user_id: int, info: SubscriptionInfo,
                      provider: str) -> Subscription:
    """Sağlayıcıdan gelen bilgiyle aboneliği oluşturur/günceller."""
    sub = db.scalars(
        select(Subscription).where(Subscription.provider_subscription_id == info.reference_code)
    ).first()
    if sub is None:
        sub = Subscription(user_id=user_id, plan=PLAN, provider=provider,
                           provider_subscription_id=info.reference_code, status=info.status)
        db.add(sub)
    sub.status = info.status
    sub.provider_customer_id = info.customer_reference_code or sub.provider_customer_id
    # Dönem sonu yalnızca ileri alınır (gecikmeli/eski bildirim geri almasın)
    if info.current_period_end and (
        sub.current_period_end is None or info.current_period_end > sub.current_period_end
    ):
        sub.current_period_end = info.current_period_end
    db.flush()
    return sub


@router.get("/plan", response_model=PlanResponse)
def plan() -> PlanResponse:
    s = get_settings()
    return PlanResponse(fiyat_metni=s.subscription_price_text, saglayici=s.payment_provider,
                        ucretsiz_arama_hakki=s.free_searches_per_month)


@router.get("/subscription", response_model=SubscriptionResponse)
def my_subscription(user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)) -> SubscriptionResponse:
    sub = latest_subscription(db, user)
    if sub is None:
        return SubscriptionResponse(var=False)
    return SubscriptionResponse(
        var=has_active_subscription(db, user, _now()),
        durum=sub.status.value,
        donem_sonu=sub.current_period_end,
        plan=sub.plan,
        iptal_edilebilir=sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE),
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(body: BillingRequest, user: User = Depends(get_verified_user),
             db: Session = Depends(get_db),
             provider: PaymentProvider = Depends(get_payment_provider)) -> CheckoutResponse:
    limit("checkout_user", str(user.id))
    if has_active_subscription(db, user, _now()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Zaten etkin bir aboneliğiniz var")
    s = get_settings()
    pc = PaymentCheckout(user_id=user.id, provider=provider.name, token="beklemede-" + str(user.id)
                         + "-" + str(int(_now().timestamp() * 1e6)), plan=PLAN)
    db.add(pc)
    db.flush()
    billing = BillingInfo(name=body.ad, surname=body.soyad, email=user.email,
                          gsm_number=body.telefon, identity_number=body.tckn,
                          address=body.adres, city=body.sehir)
    try:
        session = provider.start_checkout(
            billing, s.iyzico_plan_reference_code,
            callback_url=f"{s.backend_url.rstrip('/')}/payments/callback",
            conversation_id=f"odeme-{pc.id}",
        )
    except PaymentError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    pc.token = session.token
    db.commit()
    return CheckoutResponse(token=session.token,
                            checkout_form_content=session.checkout_form_content,
                            saglayici=provider.name)


def _redirect(result: str) -> RedirectResponse:
    url = f"{get_settings().frontend_url.rstrip('/')}/abonelik?durum={result}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/callback", include_in_schema=False)
async def callback(request: Request, db: Session = Depends(get_db),
                   provider: PaymentProvider = Depends(get_payment_provider)) -> RedirectResponse:
    """Sağlayıcının tarayıcıyı yönlendirdiği adres (application/x-www-form-urlencoded)."""
    raw = (await request.body()).decode("utf-8", errors="replace")
    token = (parse_qs(raw).get("token") or [""])[0]
    pc = db.scalars(select(PaymentCheckout).where(PaymentCheckout.token == token)).first() \
        if token else None
    if pc is None:
        return _redirect("hata")
    if pc.completed_at is not None:
        return _redirect("basarili" if pc.result == "basarili" else "hata")
    try:
        info = provider.retrieve_checkout(token)
    except PaymentError:
        pc.completed_at, pc.result = _now(), "hata"
        db.commit()
        return _redirect("hata")
    sync_subscription(db, pc.user_id, info, provider.name)
    ok = info.status == SubscriptionStatus.ACTIVE
    pc.completed_at, pc.result = _now(), ("basarili" if ok else "hata")
    db.commit()
    return _redirect(pc.result)


@router.post("/webhook/iyzico")
async def webhook(request: Request, db: Session = Depends(get_db),
                  provider: PaymentProvider = Depends(get_payment_provider)) -> dict:
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Geçersiz bildirim") from None
    try:
        event = provider.parse_webhook(payload, dict(request.headers))
    except PaymentError as exc:
        logger.warning("Ödeme bildirimi reddedildi: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bildirim doğrulanamadı") from None

    sub = db.scalars(select(Subscription).where(
        Subscription.provider_subscription_id == event.subscription_reference_code)).first()
    if sub is None:
        # Ödeme formu dönüşü henüz işlenmemiş olabilir; kullanıcıyla eşleyemeyiz.
        logger.warning("Bilinmeyen abonelik için bildirim: %s", event.subscription_reference_code)
        return {"durum": "yok_sayildi"}
    try:
        info = provider.get_subscription(event.subscription_reference_code)
    except PaymentError:
        # 5xx: sağlayıcı bildirimi yeniden dener
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Abonelik sorgulanamadı") from None
    sync_subscription(db, sub.user_id, info, provider.name)
    db.commit()
    return {"durum": "islendi"}


@router.post("/cancel", response_model=MessageResponse)
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db),
           provider: PaymentProvider = Depends(get_payment_provider)) -> MessageResponse:
    sub = latest_subscription(db, user)
    if sub is None or sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE) \
            or not sub.provider_subscription_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "İptal edilecek etkin bir abonelik yok")
    try:
        provider.cancel(sub.provider_subscription_id)
    except PaymentError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    sub.status = SubscriptionStatus.CANCELED
    db.commit()
    end = sub.current_period_end
    tail = f" Ödemesi yapılmış dönem sonuna ({end:%d.%m.%Y}) kadar sınırsız arama devam eder." \
        if end and end > _now() else ""
    return MessageResponse(mesaj="Aboneliğiniz iptal edildi; yenileme yapılmayacak." + tail)
