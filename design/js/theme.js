(function () {
  var root = document.documentElement;
  var stored = null;
  try {
    stored = localStorage.getItem("sezony-theme");
  } catch (e) {}
  if (stored === "light" || stored === "dark") {
    root.setAttribute("data-theme", stored);
  }

  function currentTheme() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function setTheme(next) {
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("sezony-theme", next);
    } catch (e) {}
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.textContent = next === "dark" ? "☾ Тёмная" : "☀ Светлая";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setTheme(currentTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    });

    // Демо-отклик на "Сделал": вспышка + тост, без переписывания состояния приложения.
    document.querySelectorAll("[data-demo-done]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var card = btn.closest(".action-card");
        if (card) {
          card.classList.add("action-card--done");
        }
        var toast = document.querySelector("[data-demo-toast]");
        if (toast) {
          toast.hidden = false;
          toast.style.animation = "none";
          void toast.offsetWidth;
          toast.style.animation = "";
          clearTimeout(window.__toastTimer);
          window.__toastTimer = setTimeout(function () {
            toast.hidden = true;
          }, 3200);
        }
      });
    });

    document.querySelectorAll("[data-open-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var modal = document.getElementById(btn.getAttribute("data-open-modal"));
        if (modal) modal.hidden = false;
      });
    });
    document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        btn.closest(".modal-scrim").hidden = true;
      });
    });
  });
})();
