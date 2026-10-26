from sqlalchemy import Column, Integer, String, Text, Float
from database import Base

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=False)
    actual_answer = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    judge_reasoning = Column(Text, nullable=True)