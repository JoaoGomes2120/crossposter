from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id            = Column(String, primary_key=True)
    open_id       = Column(String, unique=True)
    access_token  = Column(String)
    refresh_token = Column(String)
    expires_at    = Column(DateTime)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class VideoPost(Base):
    __tablename__ = "video_posts"
    id          = Column(String, primary_key=True)
    user_id     = Column(String)
    source_url  = Column(String)
    caption     = Column(String)
    status      = Column(String, default="PENDING")
    publish_id  = Column(String, nullable=True)
    error_msg   = Column(String, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    published_at= Column(DateTime, nullable=True)