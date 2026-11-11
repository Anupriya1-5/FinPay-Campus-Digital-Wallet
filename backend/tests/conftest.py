import os
os.environ["DATABASE_URL"] = "sqlite:///./test_finpay.db"
os.environ["JWT_SECRET"] = "test-secret"
import pytest
from fastapi.testclient import TestClient
from app.core.database import Base, engine
from app.main import app

@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.core.database import SessionLocal
    from app.models.models import User, Wallet, Merchant
    from app.services.security_service import hash_password
    db = SessionLocal()
    student = User(name="Test Student", email="student@test.edu", password_hash=hash_password("password123"), role="STUDENT")
    merchant_user = User(name="Test Merchant", email="merchant@test.edu", password_hash=hash_password("password123"), role="MERCHANT")
    admin = User(name="Test Admin", email="admin@test.edu", password_hash=hash_password("password123"), role="ADMIN")
    db.add_all([student, merchant_user, admin]); db.flush()
    db.add(Wallet(user_id=student.id, balance_paise=100000, tier="BASIC"))
    db.add(Merchant(owner_user_id=merchant_user.id, name="Test Canteen", category="CANTEEN", status="APPROVED"))
    db.commit(); db.close()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
