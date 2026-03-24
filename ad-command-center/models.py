from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, LargeBinary, ForeignKey
from sqlalchemy.sql import func
from db import Base

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    status = Column(String)
    daily_budget = Column(Integer)  # cents
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class AdSet(Base):
    __tablename__ = "ad_sets"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    campaign_id = Column(String, ForeignKey("campaigns.id"))
    status = Column(String)
    daily_budget = Column(Integer)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Ad(Base):
    __tablename__ = "ads"
    id = Column(String, primary_key=True)
    channel = Column(String, default="meta")
    name = Column(String)
    ad_set_id = Column(String, ForeignKey("ad_sets.id"))
    status = Column(String)
    creative_url = Column(Text)
    creative_cached = Column(LargeBinary, nullable=True)
    ad_copy = Column(Text)
    parent_ad_id = Column(String, ForeignKey("ads.id"), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String, default="meta")
    ad_id = Column(String, ForeignKey("ads.id"))
    timestamp = Column(DateTime, server_default=func.now())
    spend = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    add_to_carts = Column(Integer, default=0)
    purchases = Column(Integer, default=0)
    revenue = Column(Float, default=0)
    roas = Column(Float, default=0)

class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String, default="meta")
    timestamp = Column(DateTime, server_default=func.now())
    analysis_json = Column(Text)
    recommendations = Column(Text)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    read = Column(Boolean, default=False)

class IterationJob(Base):
    __tablename__ = "iteration_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id = Column(String, ForeignKey("ads.id"))
    status = Column(String, default="pending")  # pending/generating/launching/done/failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
