(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var circle = document.getElementById("breathing-circle");
    var label = document.getElementById("breathing-phase-label");
    if (!circle || !label) return;

    // Фазы техник (доп. задача, см. docs/decisions/DECISIONS.md → wger/guide):
    // "4-6" — 4 сек вдох / 6 сек выдох (~6 вдохов/мин, ВОЗ/физиология
    // медленного дыхания). "cyclic_sigh" — два коротких вдоха носом подряд
    // + один долгий выдох ртом (физиологический вздох).
    var TECHNIQUES = {
      "4-6": [
        { label: window.__t_inhale, seconds: 4, scale: 1 },
        { label: window.__t_exhale, seconds: 6, scale: 0.6 },
      ],
      cyclic_sigh: [
        { label: window.__t_inhale, seconds: 1.5, scale: 0.8 },
        { label: window.__t_inhale2, seconds: 1.5, scale: 1 },
        { label: window.__t_exhale, seconds: 6, scale: 0.6 },
      ],
    };

    var currentTechnique = "4-6";
    var phaseTimeoutId = null;
    var running = false;

    function runPhase(index, phases) {
      if (!running) return;
      var phase = phases[index % phases.length];
      circle.style.transform = "scale(" + phase.scale + ")";
      circle.style.opacity = phase.scale === 1 ? "0.4" : "0.2";
      label.textContent = phase.label || "";
      phaseTimeoutId = setTimeout(function () {
        runPhase(index + 1, phases);
      }, phase.seconds * 1000);
    }

    function start() {
      running = true;
      runPhase(0, TECHNIQUES[currentTechnique]);
    }

    function stop() {
      running = false;
      clearTimeout(phaseTimeoutId);
    }

    document.querySelectorAll(".breathing-technique-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        currentTechnique = btn.getAttribute("data-technique");
        document.querySelectorAll(".breathing-technique-btn").forEach(function (b) {
          b.classList.remove("btn--primary");
          b.classList.add("btn--secondary");
        });
        btn.classList.remove("btn--secondary");
        btn.classList.add("btn--primary");
      });
    });

    document.querySelectorAll(".focus-duration-btn").forEach(function (btn) {
      btn.addEventListener("click", start);
    });
    var stopBtn = document.getElementById("focus-stop");
    var saveBtn = document.getElementById("focus-save");
    if (stopBtn) stopBtn.addEventListener("click", stop);
    if (saveBtn) stop();
  });
})();
