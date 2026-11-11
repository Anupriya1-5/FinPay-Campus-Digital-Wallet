from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import Base, engine, get_db
from app.models.models import *
from app.schemas.schemas import *
from app.services.security_service import *
from app.services.ledger_service import post_ledger
from app.services.cashback_service import capped_cashback
from app.services.audit_service import audit, notify

Base.metadata.create_all(bind=engine)
app = FastAPI(title="FinPay Campus Wallet API", version="2.0.0",
              description="Academic demo wallet; no real bank or UPI integration.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"app": "FinPay", "status": "running", "docs": "/docs"}

@app.post("/auth/register")
def register_student(data: RegisterStudent, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password), role="STUDENT")
    db.add(user); db.flush()
    db.add(Wallet(user_id=user.id, balance_paise=0, tier="BASIC"))
    audit(db, user, "STUDENT_REGISTERED", "User", user.id)
    db.commit()
    return {"message": "Registration successful. Please log in."}

@app.post("/auth/merchant-register")
def register_merchant(data: MerchantRegister, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    category = data.category.upper()
    if category not in {"CANTEEN", "STATIONERY", "TRANSPORT", "HOSTEL", "ONLINE"}:
        raise HTTPException(400, "Unsupported merchant category")
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password), role="MERCHANT")
    db.add(user); db.flush()
    merchant = Merchant(owner_user_id=user.id, name=data.shop_name, category=category,
                        description=data.description, status="PENDING")
    db.add(merchant); audit(db, user, "MERCHANT_REGISTERED", "Merchant", merchant.id)
    db.commit()
    return {"message": "Merchant application submitted for admin approval."}

@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash) or not user.active:
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}

@app.get("/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}

@app.get("/wallet")
def wallet(db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    w = db.query(Wallet).filter_by(user_id=user.id).first()
    return {"balance_paise": w.balance_paise, "balance_rupees": w.balance_paise / 100, "tier": w.tier}

@app.post("/wallet/topup")
def topup(data: TopupIn, db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    w = db.query(Wallet).filter_by(user_id=user.id).first()
    amount = data.amount_rupees * 100
    ref = "TOP-" + uuid4().hex[:12].upper()
    post_ledger(db, w, "TOPUP", amount, "TOPUP", ref, "Simulated wallet top-up")
    notify(db, user.id, "Wallet topped up", f"₹{data.amount_rupees} added to your demo wallet.")
    audit(db, user, "WALLET_TOPUP", "Wallet", w.id, f"amount_paise={amount}")
    db.commit()
    return {"reference": ref, "balance_paise": w.balance_paise, "message": "Demo top-up successful"}

@app.get("/merchants")
def merchants(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Merchant).filter_by(status="APPROVED").all()
    return [{"id": m.id, "name": m.name, "category": m.category, "description": m.description} for m in rows]

@app.post("/payments")
def payment(data: PaymentIn, idempotency_key: str = Header(..., alias="Idempotency-Key"),
            db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    if not idempotency_key or len(idempotency_key) > 100:
        raise HTTPException(400, "A valid Idempotency-Key header is required")
    existing = db.query(Transaction).filter_by(student_user_id=user.id, idempotency_key=idempotency_key).first()
    if existing:
        return {"transaction_ref": existing.transaction_ref, "status": existing.status,
                "cashback_paise": existing.cashback_paise, "duplicate": True}
    merchant = db.get(Merchant, data.merchant_id)
    if not merchant or merchant.status != "APPROVED":
        raise HTTPException(404, "Approved merchant not found")
    wallet = db.query(Wallet).filter_by(user_id=user.id).with_for_update().first()
    amount = data.amount_rupees * 100
    if wallet.balance_paise < amount:
        raise HTTPException(400, "Insufficient wallet balance")
    ref = "FP-" + uuid4().hex[:12].upper()
    tx = Transaction(transaction_ref=ref, student_user_id=user.id, merchant_id=merchant.id,
                     category=merchant.category, amount_paise=amount, idempotency_key=idempotency_key)
    db.add(tx); db.flush()
    post_ledger(db, wallet, "PAYMENT_DEBIT", -amount, "TRANSACTION", ref, f"Payment to {merchant.name}")
    cb = capped_cashback(db, user.id, amount, merchant.category, wallet.tier)
    if cb:
        post_ledger(db, wallet, "CASHBACK_CREDIT", cb, "TRANSACTION", ref, "Cashback earned")
        tx.cashback_paise = cb
        db.add(CashbackRecord(user_id=user.id, transaction_id=tx.id, category=merchant.category, amount_paise=cb))
    notify(db, user.id, "Payment successful", f"₹{data.amount_rupees} paid to {merchant.name}.")
    notify(db, merchant.owner_user_id, "New payment received", f"Payment of ₹{data.amount_rupees} received.")
    # Lightweight velocity rule: flag 4+ payments in the previous 2 minutes.
    recent = db.query(Transaction).filter(Transaction.student_user_id == user.id,
        Transaction.created_at >= datetime.utcnow() - timedelta(minutes=2)).count()
    if recent >= 4:
        db.add(FraudAlert(user_id=user.id, transaction_id=tx.id, rule="RAPID_PAYMENT_VELOCITY",
                          details=f"{recent} payments detected within two minutes"))
    audit(db, user, "PAYMENT_PROCESSED", "Transaction", ref, f"merchant={merchant.name}; amount_paise={amount}")
    db.commit()
    return {"transaction_ref": ref, "status": "SUCCESS", "cashback_paise": cb,
            "balance_paise": wallet.balance_paise, "duplicate": False}

@app.get("/transactions")
def transactions(db: Session = Depends(get_db), user=Depends(current_user)):
    q = db.query(Transaction)
    if user.role == "STUDENT":
        q = q.filter(Transaction.student_user_id == user.id)
    elif user.role == "MERCHANT":
        m = db.query(Merchant).filter_by(owner_user_id=user.id).first()
        if not m: return []
        q = q.filter(Transaction.merchant_id == m.id)
    return [{"id": t.id, "reference": t.transaction_ref, "student_user_id": t.student_user_id,
             "merchant_id": t.merchant_id, "category": t.category, "amount_paise": t.amount_paise,
             "cashback_paise": t.cashback_paise, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in q.order_by(Transaction.created_at.desc()).limit(200).all()]

@app.get("/analytics/spending")
def spending(db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    rows = db.query(Transaction.category, func.sum(Transaction.amount_paise)).filter(
        Transaction.student_user_id == user.id, Transaction.status == "SUCCESS"
    ).group_by(Transaction.category).all()
    return [{"category": c, "amount_paise": int(v or 0)} for c, v in rows]

@app.get("/notifications")
def notifications(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return [{"id": n.id, "title": n.title, "message": n.message, "read": n.read,
             "created_at": n.created_at.isoformat()} for n in rows]

@app.post("/notifications/{notification_id}/read")
def read_notification(notification_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    n = db.query(Notification).filter_by(id=notification_id, user_id=user.id).first()
    if not n: raise HTTPException(404, "Notification not found")
    n.read = True; db.commit()
    return {"message": "Marked as read"}

@app.post("/refunds")
def request_refund(data: RefundIn, db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    tx = db.get(Transaction, data.transaction_id)
    if not tx or tx.student_user_id != user.id or tx.status != "SUCCESS":
        raise HTTPException(404, "Eligible successful transaction not found")
    if db.query(Refund).filter_by(transaction_id=tx.id).filter(Refund.status != "REJECTED").first():
        raise HTTPException(409, "A refund request already exists")
    refund = Refund(transaction_id=tx.id, student_user_id=user.id, reason=data.reason)
    db.add(refund); db.flush()
    complaint = Complaint(student_user_id=user.id, transaction_id=tx.id, subject="Refund request",
                          description=data.reason)
    db.add(complaint)
    notify(db, user.id, "Refund request submitted", f"Refund request #{refund.id} is under review.")
    audit(db, user, "REFUND_REQUESTED", "Refund", refund.id)
    db.commit()
    return {"refund_id": refund.id, "status": refund.status}

@app.post("/complaints")
def create_complaint(data: ComplaintIn, db: Session = Depends(get_db), user=Depends(allow_roles("STUDENT"))):
    c = Complaint(student_user_id=user.id, transaction_id=data.transaction_id,
                  subject=data.subject, description=data.description)
    db.add(c); db.flush(); audit(db, user, "COMPLAINT_CREATED", "Complaint", c.id); db.commit()
    return {"complaint_id": c.id, "status": c.status}

@app.get("/support/queue")
def support_queue(db: Session = Depends(get_db), user=Depends(allow_roles("SUPPORT", "ADMIN"))):
    rows = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    return [{"id": c.id, "student_user_id": c.student_user_id, "transaction_id": c.transaction_id,
             "subject": c.subject, "description": c.description, "status": c.status,
             "created_at": c.created_at.isoformat()} for c in rows]

@app.post("/support/complaints/{complaint_id}/review")
def review_complaint(complaint_id: int, data: ReviewIn, db: Session = Depends(get_db),
                     user=Depends(allow_roles("SUPPORT", "ADMIN"))):
    c = db.get(Complaint, complaint_id)
    if not c: raise HTTPException(404, "Complaint not found")
    decision = data.decision.upper()
    if decision not in {"UNDER_REVIEW", "APPROVED", "REJECTED", "RESOLVED"}:
        raise HTTPException(400, "Invalid decision")
    c.status = decision; c.assigned_to = user.id
    refund = None
    if c.subject == "Refund request" and c.transaction_id:
        refund = db.query(Refund).filter_by(transaction_id=c.transaction_id).first()
        if refund:
            refund.status = decision; refund.reviewed_by = user.id; refund.updated_at = datetime.utcnow()
            if decision == "APPROVED":
                tx = db.get(Transaction, c.transaction_id)
                if tx.status == "REFUNDED": raise HTTPException(409, "Transaction already refunded")
                w = db.query(Wallet).filter_by(user_id=tx.student_user_id).with_for_update().first()
                post_ledger(db, w, "REFUND_CREDIT", tx.amount_paise, "REFUND", refund.id, "Approved payment refund")
                tx.status = "REFUNDED"
                notify(db, tx.student_user_id, "Refund approved", f"Refund for {tx.transaction_ref} has been credited.")
            elif decision == "REJECTED":
                notify(db, c.student_user_id, "Refund rejected", data.note or "Your refund request was rejected.")
    audit(db, user, "COMPLAINT_REVIEWED", "Complaint", c.id, decision)
    db.commit()
    return {"complaint_id": c.id, "status": c.status}

@app.get("/merchant/me")
def merchant_me(db: Session = Depends(get_db), user=Depends(allow_roles("MERCHANT"))):
    m = db.query(Merchant).filter_by(owner_user_id=user.id).first()
    if not m: raise HTTPException(404, "Merchant profile not found")
    return {"id": m.id, "name": m.name, "category": m.category, "status": m.status, "description": m.description}

@app.get("/admin/overview")
def admin_overview(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    return {
        "users": db.query(User).count(),
        "students": db.query(User).filter_by(role="STUDENT").count(),
        "merchants": db.query(Merchant).count(),
        "pending_merchants": db.query(Merchant).filter_by(status="PENDING").count(),
        "transactions": db.query(Transaction).count(),
        "successful_volume_paise": db.query(func.coalesce(func.sum(Transaction.amount_paise), 0)).filter_by(status="SUCCESS").scalar(),
        "cashback_paise": db.query(func.coalesce(func.sum(CashbackRecord.amount_paise), 0)).scalar(),
        "open_complaints": db.query(Complaint).filter(Complaint.status.in_(["OPEN", "UNDER_REVIEW"])).count(),
        "open_fraud_alerts": db.query(FraudAlert).filter_by(status="OPEN").count()
    }

@app.get("/admin/merchants")
def admin_merchants(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    return [{"id": m.id, "owner_user_id": m.owner_user_id, "name": m.name, "category": m.category,
             "status": m.status, "description": m.description} for m in db.query(Merchant).all()]

@app.post("/admin/merchants/{merchant_id}/decision")
def merchant_decision(merchant_id: int, data: ReviewIn, db: Session = Depends(get_db),
                      user=Depends(allow_roles("ADMIN"))):
    m = db.get(Merchant, merchant_id)
    if not m: raise HTTPException(404, "Merchant not found")
    if data.decision.upper() not in {"APPROVED", "REJECTED"}: raise HTTPException(400, "Decision must be APPROVED or REJECTED")
    m.status = data.decision.upper()
    notify(db, m.owner_user_id, "Merchant application update", f"Your merchant application is {m.status.lower()}.")
    audit(db, user, "MERCHANT_DECISION", "Merchant", m.id, m.status)
    db.commit()
    return {"merchant_id": m.id, "status": m.status}

@app.get("/admin/users")
def admin_users(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active}
            for u in db.query(User).order_by(User.id).all()]

@app.post("/admin/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    target = db.get(User, user_id)
    if not target: raise HTTPException(404, "User not found")
    if target.id == user.id: raise HTTPException(400, "You cannot deactivate your own account")
    target.active = not target.active
    audit(db, user, "USER_ACTIVE_TOGGLE", "User", target.id, str(target.active))
    db.commit()
    return {"user_id": target.id, "active": target.active}

@app.get("/admin/fraud-alerts")
def fraud_alerts(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    return [{"id": a.id, "user_id": a.user_id, "transaction_id": a.transaction_id,
             "rule": a.rule, "details": a.details, "status": a.status,
             "created_at": a.created_at.isoformat()} for a in db.query(FraudAlert).order_by(FraudAlert.created_at.desc()).all()]

@app.post("/admin/fraud-alerts/{alert_id}/close")
def close_fraud(alert_id: int, db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    a = db.get(FraudAlert, alert_id)
    if not a: raise HTTPException(404, "Alert not found")
    a.status = "CLOSED"; audit(db, user, "FRAUD_ALERT_CLOSED", "FraudAlert", a.id); db.commit()
    return {"status": a.status}

@app.post("/admin/reconciliation")
def reconciliation(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    # Ledger-derived balances are compared against wallet balance snapshots.
    wallets = db.query(Wallet).all()
    issues = []
    for w in wallets:
        ledger_sum = db.query(func.coalesce(func.sum(LedgerEntry.amount_paise), 0)).filter_by(wallet_id=w.id).scalar() or 0
        if ledger_sum != w.balance_paise:
            issues.append({"wallet_id": w.id, "wallet_balance_paise": w.balance_paise, "ledger_net_paise": ledger_sum})
    total_payments = db.query(func.coalesce(func.sum(Transaction.amount_paise), 0)).filter_by(status="SUCCESS").scalar() or 0
    total_cashback = db.query(func.coalesce(func.sum(CashbackRecord.amount_paise), 0)).scalar() or 0
    report = {"generated_at": datetime.utcnow().isoformat(), "wallets_checked": len(wallets),
              "wallet_mismatches": issues, "successful_payment_volume_paise": total_payments,
              "cashback_issued_paise": total_cashback, "status": "ISSUES_FOUND" if issues else "BALANCED"}
    audit(db, user, "RECONCILIATION_RUN", "Reconciliation", "latest", report["status"])
    db.commit()
    return report

@app.get("/admin/audit-logs")
def audit_logs(db: Session = Depends(get_db), user=Depends(allow_roles("ADMIN"))):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [{"id": a.id, "actor_user_id": a.actor_user_id, "action": a.action,
             "entity_type": a.entity_type, "entity_id": a.entity_id, "details": a.details,
             "created_at": a.created_at.isoformat()} for a in rows]

@app.get("/support/refunds")
def support_refunds(db: Session = Depends(get_db), user=Depends(allow_roles("SUPPORT", "ADMIN"))):
    rows = db.query(Refund).order_by(Refund.created_at.desc()).all()
    return [{"id": r.id, "transaction_id": r.transaction_id, "student_user_id": r.student_user_id,
             "reason": r.reason, "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]
