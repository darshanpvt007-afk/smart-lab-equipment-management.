/* Applies the saved light/dark choice before the page is drawn, so there is
   no flash of the wrong theme. Loaded (not deferred) in <head>. Without a
   saved choice the operating system's setting is followed by the CSS. */
(function () {
  "use strict";
  try {
    var saved = window.localStorage.getItem("smartlab-theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) { /* storage blocked: follow the system setting */ }
})();
