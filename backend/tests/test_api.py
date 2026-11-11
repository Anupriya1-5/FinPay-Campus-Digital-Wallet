def token(client, email, role_password="password123"):
    r = client.post("/auth/login", json={"email": email, "password": role_password})
    assert r.status_code == 200
    return r.json()["access_token"]

def test_student_payment_and_duplicate(client):
    t = token(client, "student@test.edu")
    headers = {"Authorization": f"Bearer {t}", "Idempotency-Key": "same-key"}
    first = client.post("/payments", json={"merchant_id": 1, "amount_rupees": 100}, headers=headers)
    assert first.status_code == 200
    second = client.post("/payments", json={"merchant_id": 1, "amount_rupees": 100}, headers=headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

def test_student_cannot_open_admin_endpoint(client):
    t = token(client, "student@test.edu")
    r = client.get("/admin/overview", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403

def test_cashback_floor_and_rate():
    from app.services.cashback_service import calculate_cashback
    assert calculate_cashback(10001, "CANTEEN", "BASIC") == 200
    assert calculate_cashback(10000, "CANTEEN", "PREMIUM") == 400
