from sqlalchemy import Column, Integer, String, Float

from .database import Base

class APBotProcessLog(Base):
    __tablename__ = "ap_bot_process_log"

    id = Column(Integer, primary_key=True, index=True)
    runid = Column(String, index=True)
    filename = Column(String, index=True)
    voucher_id = Column(String, index=True)
    amount = Column(Float)
    invoice = Column(String, index=True)
    status = Column(String, index=True)  # e.g., 'success', 'error

    def __repr__(self):
        return f"<APBotProcessLog(id={self.id}, process_name={self.process_name}, status={self.status})>"