import json
import re
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.auth import get_user_from_token
from backend.database import SessionLocal
from backend.game import MAX_PLAYERS_DEFAULT, Player, game_manager

router = APIRouter()

BANNED_WORDS = [
    "시발", "씨발", "씨발놈", "개새끼", "새끼", "병신", "지랄", "존나", "닥쳐",
    "미친놈", "미친년", "걸레", "잡놈", "개년", "뒤져", "죽어라", "좃", "쓰레기", "꺼져",
]
# 글자 사이에 공백을 끼워 필터를 피하는 경우("시 발" 등)도 함께 걸러낸다.
_BANNED_PATTERN = re.compile(
    "|".join(r"\s*".join(re.escape(ch) for ch in w) for w in BANNED_WORDS)
) if BANNED_WORDS else None


def filter_chat_message(message: str) -> str:
    if not _BANNED_PATTERN:
        return message
    return _BANNED_PATTERN.sub(lambda m: "*" * len(m.group()), message)


async def _send(websocket: WebSocket, payload: dict):
    await websocket.send_text(json.dumps(payload, ensure_ascii=False))


async def _leave_current_room(websocket: WebSocket):
    room = getattr(websocket, "room", None)
    player: Player | None = getattr(websocket, "player", None)
    if room is None or player is None:
        return

    if room.status == "playing":
        await room.forfeit(player.user_id)

    was_finished = room.status == "finished"

    room.players.remove(player)
    websocket.room = None
    websocket.player = None
    game_manager.mark_user_left(player.user_id)

    if not room.players:
        game_manager.remove_room_if_empty(room.code)
    else:
        if room.host_id == player.user_id:
            room.host_id = room.players[0].user_id
        if was_finished:
            room.rematch_requests = set()
            await room.broadcast({"type": "opponent_left", "nickname": player.nickname})
        else:
            await room.broadcast_state()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    db: Session = SessionLocal()
    try:
        user = get_user_from_token(token, db) if token else None
    finally:
        db.close()

    # accept() first so an invalid/expired token closes with a real 4001
    # WebSocket close code the client can detect, instead of failing the
    # handshake outright (which surfaces to the browser as a generic,
    # code-less connection error indistinguishable from a network blip).
    await websocket.accept()

    if user is None:
        await websocket.close(code=4001)
        return

    websocket.room = None
    websocket.player = None

    await _send(websocket, {"type": "room_list", "rooms": game_manager.list_rooms()})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, {"type": "error", "message": "잘못된 메시지 형식입니다."})
                continue

            msg_type = msg.get("type")

            if msg_type == "list_rooms":
                await _send(websocket, {"type": "room_list", "rooms": game_manager.list_rooms()})

            elif msg_type == "create_room":
                if websocket.room is not None:
                    await _send(websocket, {"type": "error", "message": "이미 방에 참가 중입니다."})
                    continue
                if game_manager.is_user_in_room(user.id):
                    await _send(websocket, {"type": "error", "message": "다른 곳에서 이미 게임/방에 참가 중입니다."})
                    continue
                name = (msg.get("name") or f"{user.nickname}의 방").strip()[:50]
                max_players = int(msg.get("max_players") or MAX_PLAYERS_DEFAULT)
                password = (msg.get("password") or "").strip() or None

                room = game_manager.create_room(name, user.id, max_players, password)
                player = Player(user.id, user.nickname, websocket, score=user.score)
                room.players.append(player)
                websocket.room = room
                websocket.player = player
                game_manager.mark_user_joined(user.id, room.code)
                await _send(websocket, {"type": "room_joined", "room": room.public_state()})

            elif msg_type == "join_room":
                if websocket.room is not None:
                    await _send(websocket, {"type": "error", "message": "이미 방에 참가 중입니다."})
                    continue
                if game_manager.is_user_in_room(user.id):
                    await _send(websocket, {"type": "error", "message": "다른 곳에서 이미 게임/방에 참가 중입니다."})
                    continue
                code = (msg.get("room_code") or "").strip().upper()
                room = game_manager.get_room(code)
                if room is None:
                    await _send(websocket, {"type": "error", "message": "존재하지 않는 방입니다."})
                    continue
                if room.status != "waiting":
                    await _send(websocket, {"type": "error", "message": "이미 게임이 시작된 방입니다."})
                    continue
                if len(room.players) >= room.max_players:
                    await _send(websocket, {"type": "error", "message": "방이 가득 찼습니다."})
                    continue
                if room.password and room.password != (msg.get("password") or ""):
                    await _send(websocket, {"type": "error", "message": "비밀번호가 올바르지 않습니다."})
                    continue

                player = Player(user.id, user.nickname, websocket, score=user.score)
                room.players.append(player)
                websocket.room = room
                websocket.player = player
                game_manager.mark_user_joined(user.id, room.code)
                await _send(websocket, {"type": "room_joined", "room": room.public_state()})
                await room.broadcast_state()

            elif msg_type == "leave_room":
                await _leave_current_room(websocket)

            elif msg_type == "start_game":
                room = websocket.room
                if room is None:
                    await _send(websocket, {"type": "error", "message": "참가 중인 방이 없습니다."})
                    continue
                if room.host_id != user.id:
                    await _send(websocket, {"type": "error", "message": "방장만 게임을 시작할 수 있습니다."})
                    continue
                if len(room.players) < 2:
                    await _send(websocket, {"type": "error", "message": "플레이어가 2명 이상 필요합니다."})
                    continue
                if room.status != "waiting":
                    await _send(websocket, {"type": "error", "message": "이미 진행 중인 게임입니다."})
                    continue
                await room.start_game()

            elif msg_type == "rematch":
                room = websocket.room
                if room is None:
                    await _send(websocket, {"type": "error", "message": "참가 중인 방이 없습니다."})
                    continue
                await room.request_rematch(user.id)

            elif msg_type == "submit_word":
                room = websocket.room
                if room is None:
                    await _send(websocket, {"type": "error", "message": "참가 중인 방이 없습니다."})
                    continue
                await room.submit_word(user.id, str(msg.get("word") or ""))

            elif msg_type == "chat":
                room = websocket.room
                if room is None:
                    continue
                text = str(msg.get("message") or "").strip()[:200]
                if not text:
                    continue
                await room.broadcast(
                    {
                        "type": "chat",
                        "nickname": user.nickname,
                        "message": filter_chat_message(text),
                        "time": time.strftime("%H:%M:%S"),
                    }
                )

            else:
                await _send(websocket, {"type": "error", "message": f"알 수 없는 메시지 타입: {msg_type}"})

    except WebSocketDisconnect:
        await _leave_current_room(websocket)
