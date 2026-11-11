from app.core.database import Base, engine, SessionLocal
from app.models.models import User, Wallet, Merchant
from app.services.security_service import hash_password

def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count():
            print("FinPay seed data already exists; no changes made.")
            return
        accounts = [
            ("Rahul Student", "rahul@student.finpay.edu", "STUDENT"),
            ("Priya Student", "priya@student.finpay.edu", "STUDENT"),
            ("Canteen Owner", "canteen@finpay.edu", "MERCHANT"),
            ("Stationery Owner", "stationery@finpay.edu", "MERCHANT"),
            ("Transport Operator", "transport@finpay.edu", "MERCHANT"),
            ("Campus Admin", "admin@finpay.edu", "ADMIN"),
            ("Support Officer", "support@finpay.edu", "SUPPORT"),
        ]
        users = {}
        for name, email, role in accounts:
            user = User(name=name, email=email, password_hash=hash_password("password123"), role=role)
            db.add(user); db.flush(); users[email] = user
            if role == "STUDENT":
                db.add(Wallet(user_id=user.id, balance_paise=50000 if "rahul" in email else 35000, tier="BASIC"))
        merchants = [
            ("canteen@finpay.edu", "Campus Canteen", "CANTEEN"),
            ("stationery@finpay.edu", "Campus Stationery", "STATIONERY"),
            ("transport@finpay.edu", "Campus Transport", "TRANSPORT"),
        ]
        for email, name, category in merchants:
            db.add(Merchant(owner_user_id=users[email].id, name=name, category=category,
                            description="Approved demo campus merchant", status="APPROVED"))
        db.commit()
        print("FinPay database initialized with demo users, wallets and merchants.")
        print("Demo password for all accounts: password123")
    finally:
        db.close()

if __name__ == "__main__":
    run()
