(function () {
  var THEMES = { bleu: "#1d4ed8", vert: "#15803d", violet: "#6d28d9", orange: "#c2410c", rouge: "#b91c1c" };
  var KEY = "dikevia_theme";

  function valid(t) { return Object.prototype.hasOwnProperty.call(THEMES, t) ? t : "bleu"; }

  function apply(t) {
    t = valid(t);
    document.documentElement.setAttribute("data-theme", t);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) { meta = document.createElement("meta"); meta.name = "theme-color"; document.head.appendChild(meta); }
    meta.content = THEMES[t];
    document.querySelectorAll("[data-theme-choice]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-theme-choice") === t));
    });
    return t;
  }

  function load() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function save(t) { try { localStorage.setItem(KEY, t); } catch (e) {} }

  apply(load());

  document.addEventListener("DOMContentLoaded", function () {
    apply(load());
    document.querySelectorAll("[data-theme-choice]").forEach(function (b) {
      b.addEventListener("click", function () { save(apply(b.getAttribute("data-theme-choice"))); });
    });
  });
})();
