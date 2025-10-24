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


class PaylineExcelItem(Base):
    __tablename__ = "ai_bot_payline_items"

    id = Column(Integer, primary_key=True, index=True)
    tab_name = Column(String(100), nullable=False, index=True)
    hr_requestor = Column(String(100), nullable=True, index=True)
    month_requested = Column(String(100), nullable=True, index=True)
    site = Column(String(150), nullable=True, index=True)
    emplid = Column(String(50), nullable=False, index=True)
    empl_rcd = Column(Integer, nullable=False)
    ern_ded_code = Column(String(50), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    earnings_begin_dt = Column(String(20), nullable=True)
    earnings_end_dt = Column(String(20), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    status = Column(String(50), nullable=False, default="new", index=True)  # e.g., 'new', 'processed', 'error'

    def __repr__(self) -> str:
        return (
            f"<PaylineExcelItem(id={self.id}, tab_name={self.tab_name}, "
            f"emplid={self.emplid})>"
        )


class AgentRegistry(Base):
    __tablename__ = "ai_agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    instructions = Column(String, nullable=False)
    model = Column(String(100), nullable=False)
    output_type = Column(String(100), nullable=False)
    tools = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name})>"