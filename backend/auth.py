import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=100)
    nickname: str = Field(min_length=2, max_length=30)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    nickname: str


class UserProfile(BaseModel):
    username: str
    nickname: str
    total_games: int
    wins: int
    losses: int
    win_rate: float
    score: int
    current_streak: int
    best_streak: int


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증이 필요합니다.")
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰입니다.")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없습니다.")
    return user


def get_user_from_token(token: str, db: Session) -> User | None:
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 아이디입니다.")
    if db.query(User).filter(User.nickname == payload.nickname).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용 중인 닉네임입니다.")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, nickname=user.nickname)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, nickname=user.nickname)


@router.get("/me", response_model=UserProfile)
def me(user: User = Depends(get_current_user)):
    return UserProfile(
        username=user.username,
        nickname=user.nickname,
        total_games=user.total_games,
        wins=user.wins,
        losses=user.losses,
        win_rate=user.win_rate,
        score=user.score,
        current_streak=user.current_streak,
        best_streak=user.best_streak,
    )


@router.get("/check-username")
def check_username(value: str, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.username == value).first() is not None
    return {"available": not exists}


@router.get("/check-nickname")
def check_nickname(value: str, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.nickname == value).first() is not None
    return {"available": not exists}
