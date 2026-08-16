requireLogin();

let ws = null;
let currentRoom = null;
let myNickname = getNickname();
let lastTurnWasMine = false;
let lastWaitingPlayerCount = 0;

const views = {
  lobby: document.getElementById("lobby-view"),
  waiting: document.getElementById("waiting-view"),
  game: document.getElementById("game-view"),
};

function showView(name) {
  Object.values(views).forEach((v) => v.classList.add("hidden"));
  views[name].classList.remove("hidden");
  updateStepDots(name);
}

function updateStepDots(name) {
  const stepFor = { lobby: "lobby", waiting: "waiting", game: "game" };
  const current = stepFor[name];
  ["lobby", "waiting", "game"].forEach((step) => {
    const dot = document.getElementById(`step-dot-${step}`);
    if (dot) dot.classList.toggle("is-current", step === current);
  });
}

// ---------- 탭 ----------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.remove("hidden");
  });
});

function setConnStatus(text, show) {
  const el = document.getElementById("conn-status");
  el.textContent = text;
  el.classList.toggle("hidden", !show);
}

const MAX_RECONNECT_ATTEMPTS = 5;
let reconnectAttempts = 0;

function connect() {
  setConnStatus("서버에 연결 중입니다...", true);
  ws = new WebSocket(wsUrl());

  ws.onopen = () => {
    reconnectAttempts = 0;
    setConnStatus("", false);
    ws.send(JSON.stringify({ type: "list_rooms" }));
  };

  ws.onerror = (event) => {
    console.error("WebSocket 오류:", event);
  };

  ws.onclose = (event) => {
    if (event.code === 4001) {
      clearSession();
      window.location.href = "login.html";
      return;
    }

    reconnectAttempts += 1;
    if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      setConnStatus("서버에 연결할 수 없습니다. 로그인 상태가 만료되었을 수 있어요 — 다시 로그인해주세요.", true);
      clearSession();
      setTimeout(() => (window.location.href = "login.html"), 2500);
      return;
    }

    setConnStatus(`서버와의 연결이 끊어졌습니다. 재연결 시도 중... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`, true);
    setTimeout(connect, 1500);
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };
}

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
    return;
  }
  if (ws && ws.readyState === WebSocket.CONNECTING) {
    alert("서버에 아직 연결 중입니다. 잠시 후 다시 눌러주세요.");
    return;
  }
  alert("서버와 연결되어 있지 않습니다. 페이지를 새로고침 해주세요.");
}

function handleMessage(msg) {
  switch (msg.type) {
    case "room_list":
      renderRoomList(msg.rooms);
      break;
    case "room_joined":
      currentRoom = msg.room;
      onRoomUpdate(currentRoom);
      break;
    case "room_update":
      currentRoom = msg.room;
      onRoomUpdate(currentRoom);
      break;
    case "game_started":
      currentRoom = msg.room;
      lastTurnWasMine = false;
      document.getElementById("result-overlay").classList.add("hidden");
      resetGameView();
      showView("game");
      renderGameState(currentRoom);
      break;
    case "word_accepted":
      addWordChip(msg.word, msg.by, msg.definition);
      Sound.accepted();
      break;
    case "word_rejected":
      document.getElementById("word-error-msg").textContent = msg.message;
      Sound.rejected();
      break;
    case "timer":
      updateTimer(msg.seconds_left);
      if (msg.seconds_left > 0 && msg.seconds_left <= 5) {
        Sound.tick();
      }
      break;
    case "chat":
      addChatMessage(msg);
      if (msg.nickname !== myNickname) {
        Sound.chatPop();
      }
      break;
    case "game_over":
      showResult(msg);
      if (msg.result === "win") {
        Sound.win();
      } else {
        Sound.lose();
      }
      break;
    case "rematch_status":
      setRematchStatus(
        msg.waiting_for.length ? `${msg.waiting_for.join(", ")}님의 응답을 기다리는 중...` : ""
      );
      break;
    case "game_concluded":
      onGameConcluded(msg);
      break;
    case "opponent_left":
      setRematchStatus(`${msg.nickname}님이 방을 나갔습니다.`);
      document.getElementById("rematch-btn").disabled = true;
      break;
    case "error":
      alert(msg.message);
      break;
  }
}

// ---------- 방 목록 ----------

function renderRoomList(rooms) {
  const listEl = document.getElementById("room-list");
  const emptyEl = document.getElementById("room-list-empty");
  listEl.innerHTML = "";

  if (!rooms.length) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  rooms.forEach((room) => {
    const div = document.createElement("div");
    div.className = "room-item";
    div.innerHTML = `
      <div>
        <strong>${escapeHtml(room.name)}</strong>
        ${room.has_password ? '<span class="badge">🔒 비밀번호</span>' : ""}
        <div class="hint">${room.player_count} / ${room.max_players}명 · 코드 ${room.code}</div>
      </div>
      <button data-code="${room.code}" data-haspw="${room.has_password}" class="join-btn">참가</button>
    `;
    listEl.appendChild(div);
  });

  listEl.querySelectorAll(".join-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.dataset.code;
      let password = null;
      if (btn.dataset.haspw === "true") {
        password = prompt("방 비밀번호를 입력하세요") || "";
      }
      send({ type: "join_room", room_code: code, password });
    });
  });
}

document.getElementById("refresh-rooms-btn").addEventListener("click", () => {
  send({ type: "list_rooms" });
});

document.getElementById("join-by-code-btn").addEventListener("click", () => {
  const code = document.getElementById("join-code-input").value.trim().toUpperCase();
  if (!code) return;
  send({ type: "join_room", room_code: code, password: "" });
});

document.getElementById("create-room-submit-btn").addEventListener("click", () => {
  const name = document.getElementById("room-name-input").value.trim();
  const password = document.getElementById("room-password-input").value.trim();
  let maxPlayers = parseInt(document.getElementById("room-max-players-input").value, 10);
  if (!maxPlayers || maxPlayers < 2) maxPlayers = 2;
  if (maxPlayers > 8) maxPlayers = 8;
  send({ type: "create_room", name, max_players: maxPlayers, password: password || null });
});

// ---------- 대기실 ----------

function onRoomUpdate(room) {
  if (room.status === "finished") return;
  if (room.status === "playing") {
    showView("game");
    renderGameState(room);
    return;
  }

  showView("waiting");
  document.getElementById("waiting-room-name").textContent = room.name;
  document.getElementById("waiting-room-code").textContent = `코드: ${room.code}`;

  if (room.players.length > lastWaitingPlayerCount) {
    Sound.join();
  }
  lastWaitingPlayerCount = room.players.length;

  const listEl = document.getElementById("waiting-player-list");
  listEl.innerHTML = "";
  room.players.forEach((player, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="player-list-num">${i + 1}</span><span>${escapeHtml(player.nickname)}</span>`;
    listEl.appendChild(li);
  });

  document.getElementById("start-game-btn").classList.toggle("hidden", room.players.length < 2);
}

document.getElementById("leave-room-btn").addEventListener("click", () => {
  send({ type: "leave_room" });
  currentRoom = null;
  showView("lobby");
  send({ type: "list_rooms" });
});

document.getElementById("start-game-btn").addEventListener("click", () => {
  send({ type: "start_game" });
});

// ---------- 게임 ----------

function resetGameView() {
  document.getElementById("word-history").innerHTML = "";
  document.getElementById("word-count").textContent = "0";
  document.getElementById("word-error-msg").textContent = "";
  document.getElementById("chat-messages").innerHTML = "";
  document.getElementById("current-word-display").textContent = "단어를 입력하세요";
}

function renderGameState(room) {
  const rowEl = document.getElementById("players-row");
  rowEl.innerHTML = room.players
    .map((player, i) => {
      const isActive = player.nickname === room.turn_nickname;
      const isMe = player.nickname === myNickname;
      return `
        ${i > 0 ? '<span class="vs-label">VS</span>' : ""}
        <div class="player-chip ${isActive ? "active" : ""}">
          <span class="player-chip-num">${i + 1}</span>
          <span class="player-chip-info">
            <span class="player-chip-name">${escapeHtml(player.nickname)}${isMe ? " (나)" : ""}</span>
            <span class="player-chip-score">${player.score}점</span>
          </span>
        </div>
      `;
    })
    .join("");

  const banner = document.getElementById("turn-banner");
  const isMyTurn = room.turn_nickname === myNickname;
  banner.textContent = isMyTurn ? "당신의 턴입니다!" : `${room.turn_nickname}님의 턴`;
  banner.classList.toggle("my-turn", isMyTurn);

  if (isMyTurn && !lastTurnWasMine) {
    Sound.myTurn();
  }
  lastTurnWasMine = isMyTurn;

  if (room.current_word) {
    document.getElementById("current-word-display").textContent = room.current_word;
  }

  updateTimer(room.seconds_left);
}

function addWordChip(word, by, definition) {
  const historyEl = document.getElementById("word-history");
  const chip = document.createElement("span");
  chip.className = "word-chip";
  chip.title = definition || "뜻을 찾을 수 없습니다.";
  chip.innerHTML = `<strong>${escapeHtml(word)}</strong> <span class="word-chip-by">${escapeHtml(by)}</span>`;
  historyEl.appendChild(chip);
  historyEl.scrollTop = historyEl.scrollHeight;

  document.getElementById("word-count").textContent = historyEl.children.length;
  document.getElementById("current-word-display").textContent = word;
  document.getElementById("word-error-msg").textContent = "";
  document.getElementById("word-input").value = "";
}

function updateTimer(seconds) {
  const el = document.getElementById("timer-display");
  el.textContent = seconds;
  el.classList.remove("warn", "danger");
  if (seconds <= 5) el.classList.add("danger");
  else if (seconds <= 10) el.classList.add("warn");
}

document.getElementById("word-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("word-input");
  const word = input.value.trim();
  if (!word) return;
  send({ type: "submit_word", word });
});

document.getElementById("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  send({ type: "chat", message });
  input.value = "";
});

function addChatMessage(msg) {
  const el = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = `<span class="time">${msg.time}</span><span class="nick">${escapeHtml(msg.nickname)}</span>${escapeHtml(msg.message)}`;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

// ---------- 결과 ----------

function showResult(msg) {
  const overlay = document.getElementById("result-overlay");
  const title = document.getElementById("result-title");
  title.textContent = msg.result === "win" ? "승리!" : "패배";
  title.className = msg.result === "win" ? "win" : "loss";

  document.getElementById("result-icon").innerHTML = `<i data-lucide="${msg.result === "win" ? "trophy" : "frown"}"></i>`;
  refreshIcons();

  document.getElementById("result-reason").textContent = `상대: ${msg.opponent} · ${msg.reason}`;

  const wordsHtml = msg.your_words.length
    ? msg.your_words
        .map(
          (w) =>
            `<div class="used-word-row"><strong>${escapeHtml(w.word)}</strong><span class="hint">${escapeHtml(w.definition || "뜻을 찾을 수 없습니다.")}</span></div>`
        )
        .join("")
    : '<span class="hint">-</span>';

  document.getElementById("result-stats").innerHTML = `
    <div><span>총 게임 시간</span><span>${msg.duration_seconds}초</span></div>
    <div><span>사용한 단어 수</span><span>${msg.word_count}</span></div>
    <div><span>획득 점수</span><span>${msg.score_change >= 0 ? "+" : ""}${msg.score_change}</span></div>
    <div><span>연승</span><span>${msg.streak}</span></div>
    <div><span>총 점수</span><span>${msg.total_score}</span></div>
  `;
  document.getElementById("result-words").innerHTML = wordsHtml;

  const rematchBtn = document.getElementById("rematch-btn");
  if (msg.result === "win") {
    // 승리는 곧 게임 종료를 의미하므로 바로 다시 플레이 가능
    rematchBtn.disabled = false;
    rematchBtn.textContent = "다시 플레이";
    setRematchStatus("");
  } else {
    // 탈락한 시점엔 다른 플레이어들의 게임이 아직 진행 중일 수 있음 (다인전)
    rematchBtn.disabled = true;
    rematchBtn.textContent = "다시 플레이";
    setRematchStatus("남은 플레이어들의 게임이 끝나면 다시 플레이할 수 있어요...");
  }

  overlay.classList.remove("hidden");
}

function onGameConcluded(msg) {
  const overlay = document.getElementById("result-overlay");
  if (overlay.classList.contains("hidden")) return;

  const rematchBtn = document.getElementById("rematch-btn");
  rematchBtn.disabled = false;
  rematchBtn.textContent = "다시 플레이";
  setRematchStatus(msg.winner ? `${msg.winner}님의 승리로 게임이 끝났습니다.` : "게임이 종료되었습니다.");
}

function setRematchStatus(text) {
  document.getElementById("rematch-status").textContent = text;
}

document.getElementById("rematch-btn").addEventListener("click", (e) => {
  e.target.disabled = true;
  e.target.textContent = "요청 보냄";
  send({ type: "rematch" });
});

document.getElementById("rematch-lobby-btn").addEventListener("click", () => {
  send({ type: "leave_room" });
  document.getElementById("result-overlay").classList.add("hidden");
  currentRoom = null;
  showView("lobby");
  send({ type: "list_rooms" });
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

connect();
