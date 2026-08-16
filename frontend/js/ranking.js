async function loadRanking() {
  const body = document.getElementById("ranking-body");
  try {
    const rows = await apiFetch("/api/ranking");
    body.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td><span class="player-list-num">${r.rank}</span>${r.rank === 1 ? ' <i data-lucide="trophy" style="width:14px;height:14px;vertical-align:-2px"></i>' : ""}</td>
        <td>${r.nickname}</td>
        <td>${r.score}</td>
        <td>${r.wins}</td>
        <td>${r.win_rate}%</td>
        <td>${r.best_streak}</td>
      </tr>`
      )
      .join("");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6" class="hint">아직 랭킹 데이터가 없습니다.</td></tr>`;
    }
    refreshIcons();
  } catch (err) {
    body.innerHTML = `<tr><td colspan="6" class="error-msg">${err.message}</td></tr>`;
  }
}

loadRanking();
