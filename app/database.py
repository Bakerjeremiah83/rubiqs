from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ✅ Load the database URL from your .env file
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# ✅ Create a configured session class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Base class for models
Base = declarative_base()
