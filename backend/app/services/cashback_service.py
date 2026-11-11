from datetime import datetime
from sqlalchemy import func
from app.models.models import CashbackRecord

BASIC_RULES = {
    "CANTEEN": (200, 5000),       # 2%, ₹50
    "STATIONERY": (100, 2000),    # 1%, ₹20
    "TRANSPORT": (300, 10000),    # 3%, ₹100
    "HOSTEL": (50, 20000),        # 0.5%, ₹200
    "ONLINE": (100, 3000),        # 1%, ₹30
    "TOPUP": (0, 0),
}
MULTIPLIERS = {"BASIC": 100, "PRIME": 150, "PREMIUM": 200}

def calculate_cashback(amount_paise: int, category: str, tier: str) -> int:
    rate_bps, _ = BASIC_RULES.get(category.upper(), (0, 0))
    multiplier = MULTIPLIERS.get(tier.upper(), 100)
    return (amount_paise * rate_bps * multiplier) // 1_000_000

def capped_cashback(db, user_id: int, amount_paise: int, category: str, tier: str) -> int:
    category = category.upper()
    rate, basic_cap = BASIC_RULES.get(category, (0, 0))
    if not rate or not basic_cap:
        return 0
    cap = basic_cap * MULTIPLIERS.get(tier.upper(), 100) // 100
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    used = db.query(func.coalesce(func.sum(CashbackRecord.amount_paise), 0)).filter(
        CashbackRecord.user_id == user_id,
        CashbackRecord.category == category,
        CashbackRecord.created_at >= month_start
    ).scalar() or 0
    raw = calculate_cashback(amount_paise, category, tier)
    return max(0, min(raw, cap - used))
