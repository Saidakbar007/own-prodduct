(function () {
  var tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) return;

  try {
    tg.ready();
    tg.expand();
  } catch (e) {}

  // Тема Telegram -> тот же механизм, что ручной переключатель (design/js/theme.js).
  try {
    var scheme = tg.colorScheme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", scheme);
    localStorage.setItem("sezony-theme", scheme);
  } catch (e) {}

  // BackButton: виден на всех экранах, кроме четырёх корневых вкладок и гостевой главной.
  var ROOT_PATHS = ["/", "/today", "/seasons", "/team", "/profile"];
  try {
    if (tg.BackButton) {
      if (ROOT_PATHS.indexOf(window.location.pathname) === -1) {
        tg.BackButton.show();
      } else {
        tg.BackButton.hide();
      }
      tg.BackButton.onClick(function () {
        history.back();
      });
    }
  } catch (e) {}

  // Haptic feedback на ключевых кнопках ("Сделал", реакции, переключатели).
  document.addEventListener(
    "click",
    function (ev) {
      var el = ev.target.closest("[data-haptic]");
      if (!el || !tg.HapticFeedback) return;
      var kind = el.getAttribute("data-haptic");
      if (kind === "success") {
        tg.HapticFeedback.notificationOccurred("success");
      } else {
        tg.HapticFeedback.impactOccurred(kind || "light");
      }
    },
    true
  );

  // MainButton "Сделал" на "Сегодня" — дублирует обычную кнопку формы.
  var doneForm = document.getElementById("today-done-form");
  if (doneForm && tg.MainButton) {
    var label = doneForm.getAttribute("data-main-button-label") || "Сделал";
    tg.MainButton.setText(label);
    tg.MainButton.show();
    tg.MainButton.onClick(function () {
      if (doneForm.requestSubmit) doneForm.requestSubmit();
      else doneForm.submit();
    });
  } else if (tg.MainButton) {
    tg.MainButton.hide();
  }
})();
