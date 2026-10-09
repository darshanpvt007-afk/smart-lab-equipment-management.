/* Small progressive enhancements. Every page works without this file:
   forms submit normally and the server (and the stored procedures) do all
   validation. */
(function () {
  "use strict";

  // Mobile: show / hide the sidebar.
  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // "/" focuses the global search (unless the user is typing in a field).
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (e.key === "/" && !/^(input|select|textarea)$/.test(tag)) {
      var box = document.getElementById("global-search");
      if (box) { e.preventDefault(); box.focus(); }
    }
  });

  // <select data-autosubmit> submits its form when changed (rows per page).
  document.querySelectorAll("select[data-autosubmit]").forEach(function (sel) {
    sel.addEventListener("change", function () { sel.form.submit(); });
  });

  // Ctrl+Enter (or Cmd+Enter) submits forms marked data-ctrl-enter.
  document.querySelectorAll("form[data-ctrl-enter]").forEach(function (form) {
    form.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
      }
    });
  });

  // ---- Issue form: quick due dates, pre-issue checks and summary ----
  var form = document.getElementById("issue-form");
  if (!form) { return; }
  var eq = form.querySelector("#equipment_id");
  var st = form.querySelector("#student_id");
  var issued = form.querySelector("#allocation_date");
  var due = form.querySelector("#expected_return_date");
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function parse(value) {             // "2026-10-17" -> Date at local midnight
    var p = (value || "").split("-");
    return p.length === 3 ? new Date(+p[0], +p[1] - 1, +p[2]) : null;
  }
  function iso(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function pretty(d) { return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear(); }

  function setCheck(name, state, detail) {
    var li = form.querySelector('[data-check="' + name + '"]');
    li.className = "check-" + state;   // ok | bad | todo
    li.querySelector("small").textContent = detail;
  }

  function update() {
    var e = eq.options[eq.selectedIndex];
    var s = st.options[st.selectedIndex];
    var a = parse(issued.value), b = parse(due.value);

    if (e && e.value) {
      setCheck("item", "ok", e.dataset.lab);
      var damaged = e.dataset.condition === "Damaged";
      setCheck("condition", damaged ? "bad" : "ok", "Condition: " + e.dataset.condition);
      document.getElementById("sum-item").textContent = e.dataset.serial;
    } else {
      setCheck("item", "todo", "Only Available items are offered");
      setCheck("condition", "todo", "Condition: -");
      document.getElementById("sum-item").textContent = "-";
    }

    if (a && b) {
      var days = Math.round((b - a) / 86400000);
      setCheck("dates", days >= 0 ? "ok" : "bad",
               days >= 0 ? days + "-day loan" : "Due date is " + (-days) + " day(s) before the issue date");
      document.getElementById("sum-due").textContent = pretty(b);
    } else {
      setCheck("dates", "todo", "-");
      document.getElementById("sum-due").textContent = "-";
    }

    if (s && s.value) {
      var holding = +s.dataset.holding, overdue = +s.dataset.overdue;
      setCheck("student", overdue ? "bad" : "ok",
               s.dataset.meta + " · holds " + holding + " item(s)" + (overdue ? ", " + overdue + " overdue" : ""));
      document.getElementById("sum-student").textContent = s.dataset.name;
    } else {
      setCheck("student", "todo", "Choose a student");
      document.getElementById("sum-student").textContent = "-";
    }

    form.querySelectorAll("[data-due-days]").forEach(function (chip) {
      var target = a ? iso(new Date(a.getFullYear(), a.getMonth(), a.getDate() + +chip.dataset.dueDays)) : "";
      chip.classList.toggle("chip-selected", target !== "" && target === due.value);
    });
  }

  form.querySelectorAll("[data-due-days]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      var a = parse(issued.value);
      if (!a) { return; }
      due.value = iso(new Date(a.getFullYear(), a.getMonth(), a.getDate() + +chip.dataset.dueDays));
      update();
    });
  });
  [eq, st, issued, due].forEach(function (el) {
    el.addEventListener("change", update);
    el.addEventListener("input", update);
  });
  update();
})();
