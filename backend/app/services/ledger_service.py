from app.models.models import LedgerEntry

def post_ledger(db, wallet, entry_type, amount_paise, reference_type, reference_id, note=""):
    wallet.balance_paise += amount_paise
    entry = LedgerEntry(wallet_id=wallet.id, entry_type=entry_type, amount_paise=amount_paise,
                        balance_after_paise=wallet.balance_paise, reference_type=reference_type,
                        reference_id=str(reference_id), note=note)
    db.add(entry)
    return entry
