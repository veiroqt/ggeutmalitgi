from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(30), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    total_games = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    score = Column(Integer, default=0, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    best_streak = Column(Integer, default=0, nullable=False)

    game_records = relationship("GameRecord", back_populates="user")

    @property
    def win_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return round(self.wins / self.total_games * 100, 1)


class GameRecord(Base):
    __tablename__ = "game_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    opponent_nickname = Column(String(30), nullable=False)
    result = Column(String(10), nullable=False)  # "win" or "loss"
    words_used = Column(Text, nullable=False)  # JSON-encoded list of words
    word_count = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Integer, default=0, nullable=False)
    score_change = Column(Integer, default=0, nullable=False)
    streak_after = Column(Integer, default=0, nullable=False)
    played_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="game_records")
