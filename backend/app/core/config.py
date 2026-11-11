import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finpay.db")
JWT_SECRET = os.getenv("JWT_SECRET", "local-demo-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "720"))
