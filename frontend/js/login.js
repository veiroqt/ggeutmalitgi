document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("error-msg");
  errorEl.textContent = "";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setSession(data.access_token, data.nickname);
    window.location.href = "lobby.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
