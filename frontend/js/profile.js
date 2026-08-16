requireLogin();

async function loadProfile() {
  try {
    const me = await apiFetch("/api/auth/me");
    document.getElementById("profile-nickname").textContent = `${me.nickname}님의 마이페이지`;
    document.getElementById("stat-score").textContent = me.score;
    document.getElementById("stat-total").textContent = me.total_games;
    document.getElementById("stat-winrate").textContent = `${me.win_rate}%`;
    document.getElementById("stat-streak").textContent = me.best_streak;
    document.getElementById("wl-summary").textContent = `승 ${me.wins} · 패 ${me.losses} · 현재 연승 ${me.current_streak}`;
  } catch (err) {
    alert(err.message);
  }

  try {
    const records = await apiFetch("/api/profile/records");
    const body = document.getElementById("records-body");
    body.innerHTML = records
      .map(
        (r) => `
      <tr>
        <td><span class="badge ${r.result}">${r.result === "win" ? "승리" : "패배"}</span></td>
        <td>${r.opponent_nickname}</td>
        <td>${r.word_count}</td>
        <td>${r.score_change >= 0 ? "+" : ""}${r.score_change}</td>
        <td>${new Date(r.played_at).toLocaleString("ko-KR")}</td>
      </tr>`
      )
      .join("");
    if (!records.length) {
      body.innerHTML = `<tr><td colspan="5" class="hint">아직 게임 기록이 없습니다.</td></tr>`;
    }
  } catch (err) {
    document.getElementById("records-body").innerHTML = `<tr><td colspan="5" class="error-msg">${err.message}</td></tr>`;
  }
}

loadProfile();
