(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var picker = document.getElementById("focus-picker");
    var timerView = document.getElementById("focus-timer");
    var doneView = document.getElementById("focus-done");
    var clock = document.getElementById("focus-clock");
    var status = document.getElementById("focus-status");
    var distractedBtn = document.getElementById("focus-distracted");
    var stopBtn = document.getElementById("focus-stop");
    var saveBtn = document.getElementById("focus-save");
    var form = document.getElementById("focus-complete-form");
    var minutesInput = document.getElementById("focus-minutes-input");
    var minimalInput = document.getElementById("focus-minimal-input");

    if (!picker || !timerView || !doneView) return;

    var totalSeconds = 0;
    var remaining = 0;
    var intervalId = null;

    function formatClock(seconds) {
      var m = Math.floor(seconds / 60);
      var s = seconds % 60;
      return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    function updateClock() {
      clock.textContent = formatClock(Math.max(0, remaining));
    }

    function finishBlock() {
      clearInterval(intervalId);
      timerView.style.display = "none";
      doneView.style.display = "flex";
      minutesInput.value = (totalSeconds / 60).toFixed(1);
      minimalInput.value = "false";
      if (navigator.vibrate) navigator.vibrate(200);
    }

    function tick() {
      remaining -= 1;
      updateClock();
      if (remaining <= 0) finishBlock();
    }

    function startBlock(minutes) {
      totalSeconds = minutes * 60;
      remaining = totalSeconds;
      picker.style.display = "none";
      timerView.style.display = "flex";
      updateClock();
      clearInterval(intervalId);
      intervalId = setInterval(tick, 1000);
    }

    document.querySelectorAll(".focus-duration-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        startBlock(parseInt(btn.getAttribute("data-minutes"), 10));
      });
    });

    if (distractedBtn) {
      distractedBtn.addEventListener("click", function () {
        remaining = totalSeconds;
        updateClock();
        if (navigator.vibrate) navigator.vibrate(100);
      });
    }

    if (stopBtn) {
      stopBtn.addEventListener("click", function () {
        clearInterval(intervalId);
        var elapsedSeconds = totalSeconds - remaining;
        if (elapsedSeconds < 60) {
          window.location.href = "/today";
          return;
        }
        minutesInput.value = (elapsedSeconds / 60).toFixed(1);
        minimalInput.value = "true";
        form.submit();
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        form.submit();
      });
    }
  });
})();
