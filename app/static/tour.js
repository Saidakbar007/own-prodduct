(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var steps = window.__tourSteps || [];
    var sheet = document.getElementById("tour-sheet");
    if (!sheet || !steps.length) return;

    var i = 0;
    var highlighted = null;

    function clearHighlight() {
      if (highlighted) {
        highlighted.classList.remove("tour-highlight");
        highlighted = null;
      }
    }

    function show(index) {
      clearHighlight();
      var step = steps[index];
      if (!step) return;
      var el = document.querySelector(step.selector);
      if (el) {
        el.classList.add("tour-highlight");
        highlighted = el;
        el.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      document.getElementById("tour-step-counter").textContent = (index + 1) + "/" + steps.length;
      document.getElementById("tour-title").textContent = step.title;
      document.getElementById("tour-text").textContent = step.text;
      document.getElementById("tour-next").textContent =
        index === steps.length - 1 ? sheet.getAttribute("data-done-label") : sheet.getAttribute("data-next-label");
    }

    function end() {
      clearHighlight();
      sheet.hidden = true;
    }

    sheet.hidden = false;
    show(i);

    document.getElementById("tour-next").addEventListener("click", function () {
      i += 1;
      if (i >= steps.length) {
        end();
      } else {
        show(i);
      }
    });
    document.getElementById("tour-skip").addEventListener("click", end);
  });
})();
