"""끝말잇기 게임의 핵심 규칙과 방 상태를 관리하는 모듈.

Frontend는 상태를 보여주는 역할만 하고, 모든 판정은 여기서 이루어진다.
"""

import asyncio
import json
import random
import string
import time

from backend.database import SessionLocal
from backend.dictionary_api import DictionaryAPIError, get_cached_definition, is_valid_word
from backend.hangul import chain_start_options
from backend.models import GameRecord, User

TURN_SECONDS = 15
WIN_SCORE = 100
LOSS_SCORE = 20
STREAK_BONUS_PER_WIN = 10
MAX_PLAYERS_DEFAULT = 2


def generate_room_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def get_user_score(user_id: int) -> int:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user.score if user else 0
    finally:
        db.close()


class Player:
    def __init__(self, user_id: int, nickname: str, websocket, score: int = 0):
        self.user_id = user_id
        self.nickname = nickname
        self.websocket = websocket
        self.words: list[str] = []
        self.score = score

    async def send(self, payload: dict):
        try:
            await self.websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass


class Room:
    def __init__(self, code: str, name: str, host_id: int, max_players: int, password: str | None):
        self.code = code
        self.name = name
        self.host_id = host_id
        self.max_players = max_players
        self.password = password
        self.players: list[Player] = []
        self.status = "waiting"  # waiting | playing | finished

        self.current_word: str | None = None
        self.used_words: list[str] = []
        self.word_definitions: dict[str, str | None] = {}
        self.turn_index = 0
        self.turn_deadline: float = 0.0
        self.started_at: float = 0.0
        self._timer_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.rematch_requests: set[int] = set()

    def public_summary(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "player_count": len(self.players),
            "max_players": self.max_players,
            "has_password": bool(self.password),
            "status": self.status,
        }

    def public_state(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "players": [{"nickname": p.nickname, "score": p.score} for p in self.players],
            "host_id": self.host_id,
            "current_word": self.current_word,
            "used_words": self.used_words,
            "word_definitions": self.word_definitions,
            "turn_nickname": self.players[self.turn_index].nickname if self.players and self.status == "playing" else None,
            "seconds_left": max(0, round(self.turn_deadline - time.time())) if self.status == "playing" else TURN_SECONDS,
        }

    async def broadcast(self, payload: dict, exclude: Player | None = None):
        for p in self.players:
            if p is not exclude:
                await p.send(payload)

    async def broadcast_state(self):
        await self.broadcast({"type": "room_update", "room": self.public_state()})

    def find_player(self, user_id: int) -> Player | None:
        for p in self.players:
            if p.user_id == user_id:
                return p
        return None

    async def start_game(self):
        self.status = "playing"
        self.current_word = None
        self.used_words = []
        self.word_definitions = {}
        self.turn_index = 0
        self.started_at = time.time()
        self.rematch_requests = set()
        for p in self.players:
            p.words = []
            p.score = get_user_score(p.user_id)
        await self.broadcast({"type": "game_started", "room": self.public_state()})
        self._reset_timer()

    async def request_rematch(self, user_id: int):
        async with self._lock:
            if self.status != "finished":
                await self._send_error(user_id, "지금은 다시 플레이를 요청할 수 없습니다.")
                return
            if len(self.players) < 2:
                await self._send_error(user_id, "상대방이 방을 나갔습니다.")
                return
            if self.find_player(user_id) is None:
                return

            self.rematch_requests.add(user_id)
            all_ids = {p.user_id for p in self.players}

            if self.rematch_requests >= all_ids:
                await self.start_game()
            else:
                await self.broadcast(
                    {
                        "type": "rematch_status",
                        "waiting_for": [p.nickname for p in self.players if p.user_id not in self.rematch_requests],
                    }
                )

    def _reset_timer(self):
        self.turn_deadline = time.time() + TURN_SECONDS
        if self._timer_task:
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._run_timer())

    async def _run_timer(self):
        try:
            remaining = self.turn_deadline - time.time()
            while remaining > 0:
                await asyncio.sleep(min(1.0, remaining))
                remaining = self.turn_deadline - time.time()
                if self.status != "playing":
                    return
                await self.broadcast(
                    {"type": "timer", "seconds_left": max(0, round(remaining))}
                )
            await self._handle_timeout()
        except asyncio.CancelledError:
            pass

    async def _handle_timeout(self):
        async with self._lock:
            if self.status != "playing":
                return
            loser = self.players[self.turn_index]
            winner = self.players[(self.turn_index + 1) % len(self.players)]
            await self._end_game(winner, loser, reason="시간 초과")

    async def submit_word(self, user_id: int, word: str):
        async with self._lock:
            if self.status != "playing":
                await self._send_error(user_id, "게임이 진행 중이 아닙니다.")
                return

            current_player = self.players[self.turn_index]
            if current_player.user_id != user_id:
                await self._send_error(user_id, "당신의 턴이 아닙니다.")
                return

            if time.time() > self.turn_deadline:
                await self._send_error(user_id, "제한시간이 지났습니다.")
                return

            word = word.strip()

            if not word or len(word) < 2 or not all("가" <= ch <= "힣" for ch in word):
                await self._send_error(user_id, "허용되지 않는 단어입니다. 2글자 이상의 한글 단어를 입력해주세요.")
                return

            if self.current_word:
                allowed_starts = chain_start_options(self.current_word[-1])
                if word[0] not in allowed_starts:
                    starts_desc = " 또는 ".join(f"'{ch}'" for ch in sorted(allowed_starts))
                    await self._send_error(user_id, f"{starts_desc}로 시작하는 단어를 입력해주세요.")
                    return

            if word in self.used_words:
                await self._send_error(user_id, "이미 사용된 단어입니다.")
                return

            try:
                valid = await is_valid_word(word)
            except DictionaryAPIError as exc:
                await self._send_error(user_id, str(exc))
                return

            if not valid:
                await self._send_error(user_id, "사전에 존재하지 않는 단어입니다.")
                return

            definition = get_cached_definition(word)

            self.current_word = word
            self.used_words.append(word)
            self.word_definitions[word] = definition
            current_player.words.append(word)
            self.turn_index = (self.turn_index + 1) % len(self.players)

            await self.broadcast(
                {
                    "type": "word_accepted",
                    "word": word,
                    "by": current_player.nickname,
                    "definition": definition,
                }
            )
            self._reset_timer()
            await self.broadcast_state()

    async def _send_error(self, user_id: int, message: str):
        player = self.find_player(user_id)
        if player:
            await player.send({"type": "word_rejected", "message": message})

    async def forfeit(self, user_id: int):
        """게임 중 접속이 끊긴 플레이어를 패배 처리한다."""
        async with self._lock:
            if self.status != "playing" or len(self.players) < 2:
                return
            loser = self.find_player(user_id)
            if loser is None:
                return
            winner = next(p for p in self.players if p.user_id != user_id)
            await self._end_game(winner, loser, reason="상대방 연결 끊김")

    async def _end_game(self, winner: Player, loser: Player, reason: str):
        self.status = "finished"
        if self._timer_task:
            self._timer_task.cancel()
        duration = round(time.time() - self.started_at)

        winner_result = _apply_result(winner.user_id, won=True)
        loser_result = _apply_result(loser.user_id, won=False)

        winner_words = [{"word": w, "definition": self.word_definitions.get(w)} for w in winner.words]
        loser_words = [{"word": w, "definition": self.word_definitions.get(w)} for w in loser.words]

        save_game_record(winner.user_id, loser.nickname, "win", winner_words, duration, winner_result["score_change"], winner_result["streak"])
        save_game_record(loser.user_id, winner.nickname, "loss", loser_words, duration, loser_result["score_change"], loser_result["streak"])

        await winner.send(
            {
                "type": "game_over",
                "result": "win",
                "reason": reason,
                "opponent": loser.nickname,
                "duration_seconds": duration,
                "your_words": winner_words,
                "word_count": len(winner.words),
                "score_change": winner_result["score_change"],
                "streak": winner_result["streak"],
                "total_score": winner_result["total_score"],
            }
        )
        await loser.send(
            {
                "type": "game_over",
                "result": "loss",
                "reason": reason,
                "opponent": winner.nickname,
                "duration_seconds": duration,
                "your_words": loser_words,
                "word_count": len(loser.words),
                "score_change": loser_result["score_change"],
                "streak": loser_result["streak"],
                "total_score": loser_result["total_score"],
            }
        )


def _apply_result(user_id: int, won: bool) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return {"score_change": 0, "streak": 0, "total_score": 0}

        user.total_games += 1
        if won:
            user.wins += 1
            user.current_streak += 1
            user.best_streak = max(user.best_streak, user.current_streak)
            score_change = WIN_SCORE + (user.current_streak - 1) * STREAK_BONUS_PER_WIN
        else:
            user.losses += 1
            user.current_streak = 0
            score_change = LOSS_SCORE

        user.score += score_change
        db.commit()
        return {
            "score_change": score_change,
            "streak": user.current_streak,
            "total_score": user.score,
        }
    finally:
        db.close()


def save_game_record(user_id: int, opponent_nickname: str, result: str, words: list[str], duration: int, score_change: int, streak: int):
    db = SessionLocal()
    try:
        record = GameRecord(
            user_id=user_id,
            opponent_nickname=opponent_nickname,
            result=result,
            words_used=json.dumps(words, ensure_ascii=False),
            word_count=len(words),
            duration_seconds=duration,
            score_change=score_change,
            streak_after=streak,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


class GameManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.user_room: dict[int, str] = {}

    def list_rooms(self) -> list[dict]:
        return [r.public_summary() for r in self.rooms.values() if r.status == "waiting"]

    def create_room(self, name: str, host_id: int, max_players: int, password: str | None) -> Room:
        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()
        room = Room(code, name, host_id, max_players or MAX_PLAYERS_DEFAULT, password)
        self.rooms[code] = room
        return room

    def get_room(self, code: str) -> Room | None:
        return self.rooms.get(code)

    def remove_room_if_empty(self, code: str):
        room = self.rooms.get(code)
        if room and not room.players:
            del self.rooms[code]

    def is_user_in_room(self, user_id: int) -> bool:
        return user_id in self.user_room

    def mark_user_joined(self, user_id: int, code: str):
        self.user_room[user_id] = code

    def mark_user_left(self, user_id: int):
        self.user_room.pop(user_id, None)


game_manager = GameManager()
