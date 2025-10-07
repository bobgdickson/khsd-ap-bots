from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, func

from .database import Base


class BotProcessLog(Base):
    __tablename__ = "ai_bot_process_log"

    id = Column(Integer, primary_key=True, index=True)
    runid = Column(String(100), index=True)
    filename = Column(String(255), index=True)
    voucher_id = Column(String(100), index=True)
    amount = Column(Float)
    invoice = Column(String(100), index=True)
    status = Column(String(50), index=True)  # e.g., 'success', 'error'

    def __repr__(self) -> str:
        return f"<BotProcessLog(id={self.id}, runid={self.runid}, status={self.status})>"


class BotRun(Base):
    __tablename__ = "ai_bot_runs"

    id = Column(Integer, primary_key=True, index=True)
    runid = Column(String(100), unique=True, nullable=False, index=True)
    bot_name = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending", index=True)
    cancel_requested = Column(Boolean, nullable=False, default=False, index=True)
    test_mode = Column(Boolean, nullable=False, default=False)
    context = Column(JSON, nullable=True)
    message = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BotRun(runid={self.runid}, bot_name={self.bot_name}, status={self.status})>"

