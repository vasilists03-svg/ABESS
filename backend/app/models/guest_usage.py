from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database import Base


class GuestUsage(Base):
    __tablename__ = "guest_usage"

    id = Column(Integer, primary_key=True, index=True)

    guest_id = Column(String, unique=True, index=True, nullable=False)
    solve_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)