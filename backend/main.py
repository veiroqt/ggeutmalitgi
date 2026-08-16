import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.auth import get_current_user, router as auth_router
from backend.database import get_db, init_db
from backend.models import GameRecord, User
from backend.websocket import router as ws_router

app = FastAPI(title="끝말잇기")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ws_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/ranking")
def ranking(limit: int = 50, db: Session = Depends(get_db)):
    users = (
        db.query(User)
        .order_by(User.score.desc(), User.wins.desc(), User.best_streak.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "rank": i + 1,
            "nickname": u.nickname,
            "score": u.score,
            "wins": u.wins,
            "total_games": u.total_games,
            "win_rate": u.win_rate,
            "best_streak": u.best_streak,
        }
        for i, u in enumerate(users)
    ]


@app.get("/api/debug/dict-check")
async def debug_dict_check(word: str = "사과"):
    """배포 환경에서 사전 API 연동 상태를 점검하기 위한 임시 진단용 엔드포인트."""
    import os

    import httpx

    from backend.dictionary_api import API_URL

    api_key = os.environ.get("KOREAN_DICT_API_KEY")
    key_info = f"present, length={len(api_key)}" if api_key else "MISSING"

    if not api_key:
        return {"key_info": key_info}

    params = {"key": api_key, "q": word, "req_type": "json"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(API_URL, params=params)
            return {
                "key_info": key_info,
                "http_status": resp.status_code,
                "body_length": len(resp.text),
                "body_preview": resp.text[:1500],
            }
    except Exception as exc:
        return {"key_info": key_info, "exception": str(exc)}


@app.get("/api/profile/records")
def my_records(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = (
        db.query(GameRecord)
        .filter(GameRecord.user_id == user.id)
        .order_by(GameRecord.played_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "opponent_nickname": r.opponent_nickname,
            "result": r.result,
            "words_used": json.loads(r.words_used),
            "word_count": r.word_count,
            "duration_seconds": r.duration_seconds,
            "score_change": r.score_change,
            "streak_after": r.streak_after,
            "played_at": r.played_at.isoformat() if r.played_at else None,
        }
        for r in records
    ]


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
