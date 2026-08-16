function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

async function checkAvailability(field, value, hintEl) {
  if (!value) {
    hintEl.textContent = "";
    return;
  }
  try {
    const data = await apiFetch(`/api/auth/check-${field}?value=${encodeURIComponent(value)}`);
    if (data.available) {
      hintEl.textContent = "사용 가능합니다.";
      hintEl.className = "hint ok";
    } else {
      hintEl.textContent = "이미 사용 중입니다.";
      hintEl.className = "hint bad";
    }
  } catch (e) {
    hintEl.textContent = "";
  }
}

const usernameInput = document.getElementById("username");
const nicknameInput = document.getElementById("nickname");
const usernameHint = document.getElementById("username-hint");
const nicknameHint = document.getElementById("nickname-hint");

usernameInput.addEventListener(
  "input",
  debounce(() => checkAvailability("username", usernameInput.value.trim(), usernameHint), 400)
);
nicknameInput.addEventListener(
  "input",
  debounce(() => checkAvailability("nickname", nicknameInput.value.trim(), nicknameHint), 400)
);

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-msg");
  errorEl.textContent = "";

  const username = usernameInput.value.trim();
  const nickname = nicknameInput.value.trim();
  const password = document.getElementById("password").value;
  const password2 = document.getElementById("password2").value;

  if (password !== password2) {
    errorEl.textContent = "비밀번호가 일치하지 않습니다.";
    return;
  }

  try {
    const data = await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, nickname }),
    });
    setSession(data.access_token, data.nickname);
    window.location.href = "lobby.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
