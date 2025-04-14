# run_once_reset_db.py

from app.models import Base
from app.storage import engine

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Database reset complete.")
