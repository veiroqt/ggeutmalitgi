const Sound = (() => {
  let ctx = null;

  function getCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      ctx = new AC();
    }
    if (ctx.state === "suspended") {
      ctx.resume();
    }
    return ctx;
  }

  document.addEventListener("click", () => getCtx(), { once: true });

  function isMuted() {
    return localStorage.getItem("muted") === "1";
  }

  function setMuted(muted) {
    localStorage.setItem("muted", muted ? "1" : "0");
  }

  function tone(freq, start, duration, type = "sine", gainPeak = 0.18) {
    if (isMuted()) return;
    const c = getCtx();
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    const t0 = c.currentTime + start;
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(gainPeak, t0 + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, t0 + duration);
    osc.connect(gain);
    gain.connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + duration + 0.05);
  }

  return {
    isMuted,
    setMuted,
    accepted() {
      tone(523.25, 0, 0.1);
      tone(783.99, 0.09, 0.14);
    },
    rejected() {
      tone(220, 0, 0.09, "sawtooth", 0.15);
      tone(160, 0.08, 0.18, "sawtooth", 0.15);
    },
    myTurn() {
      tone(659.25, 0, 0.09, "triangle");
      tone(880, 0.1, 0.14, "triangle");
    },
    tick() {
      tone(440, 0, 0.06, "square", 0.08);
    },
    win() {
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, i * 0.12, 0.18));
    },
    lose() {
      [392, 349.23, 293.66].forEach((f, i) => tone(f, i * 0.16, 0.28, "sine", 0.15));
    },
    join() {
      tone(600, 0, 0.08, "sine", 0.12);
    },
    chatPop() {
      tone(1000, 0, 0.04, "sine", 0.06);
    },
  };
})();
