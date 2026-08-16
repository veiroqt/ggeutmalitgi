const API_BASE = "";

function getToken() {
  return localStorage.getItem("token");
}

function getNickname() {
  return localStorage.getItem("nickname");
}

function setSession(token, nickname) {
  localStorage.setItem("token", token);
  localStorage.setItem("nickname", nickname);
}

function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("nickname");
}

function requireLogin() {
  if (!getToken()) {
    window.location.href = "login.html";
  }
}

async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, { ...options, headers });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    data = null;
  }

  if (!res.ok) {
    const message = (data && data.detail) || "요청 처리 중 오류가 발생했습니다.";
    throw new Error(message);
  }
  return data;
}

function wsUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(getToken() || "")}`;
}

function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderNavbar(activePage) {
  const el = document.getElementById("navbar");
  if (!el) return;
  const nickname = getNickname();
  const loggedIn = !!getToken();

  const soundOn = typeof Sound === "undefined" || !Sound.isMuted();

  const cls = (page) => (activePage === page ? "active" : "");

  el.innerHTML = `
    <div class="logo">
      <a href="index.html">
        <span class="logo-mark">끝</span>
        <span>끝말<span>잇기</span></span>
      </a>
    </div>
    <nav>
      <a href="lobby.html" class="${cls("lobby")}"><i data-lucide="gamepad-2"></i>게임하기</a>
      <a href="ranking.html" class="${cls("ranking")}"><i data-lucide="trophy"></i>랭킹</a>
      ${loggedIn ? `<a href="profile.html" class="${cls("profile")}"><i data-lucide="user"></i>마이페이지</a>` : ""}
      ${loggedIn
        ? `<a href="#" id="nav-logout"><i data-lucide="log-out"></i>${nickname}님 로그아웃</a>`
        : `<a href="login.html" class="${cls("login")}"><i data-lucide="log-in"></i>로그인</a>`}
      ${typeof Sound !== "undefined" ? `<a href="#" id="nav-sound-toggle"><i data-lucide="${soundOn ? "volume-2" : "volume-x"}"></i></a>` : ""}
    </nav>
  `;

  const logoutBtn = document.getElementById("nav-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", (e) => {
      e.preventDefault();
      clearSession();
      window.location.href = "index.html";
    });
  }

  const soundBtn = document.getElementById("nav-sound-toggle");
  if (soundBtn) {
    soundBtn.addEventListener("click", (e) => {
      e.preventDefault();
      Sound.setMuted(!Sound.isMuted());
      soundBtn.innerHTML = `<i data-lucide="${Sound.isMuted() ? "volume-x" : "volume-2"}"></i>`;
      refreshIcons();
    });
  }

  refreshIcons();
}
