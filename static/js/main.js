/* CMIMS front-end helpers.
 *
 * Deliberately small and dependency-free: the application works fully without
 * JavaScript.  Everything here is progressive enhancement - confirmation
 * dialogs, the mobile navigation drawer, dismissing alerts and auto-submitting
 * filter dropdowns.
 */
(function () {
  "use strict";

  /* ------------------------------------------------- mobile navigation */
  function initSidebar() {
    document.querySelectorAll("[data-sidebar-toggle]").forEach(function (el) {
      el.addEventListener("click", function () {
        document.body.classList.toggle("sidebar-open");
        var backdrop = document.querySelector(".sidebar-backdrop");
        if (backdrop) {
          backdrop.hidden = !document.body.classList.contains("sidebar-open");
        }
      });
    });
  }

  /* ----------------------------------------------------- dismiss alerts */
  function initAlerts() {
    document.querySelectorAll("[data-dismiss]").forEach(function (button) {
      button.addEventListener("click", function () {
        var alert = button.closest(".alert");
        if (alert) {
          alert.remove();
        }
      });
    });

    // Success/info messages fade away on their own after a while.
    document.querySelectorAll(".alert-success, .alert-info").forEach(function (alert) {
      window.setTimeout(function () {
        alert.style.transition = "opacity .4s ease";
        alert.style.opacity = "0";
        window.setTimeout(function () { alert.remove(); }, 400);
      }, 6000);
    });
  }

  /* ------------------------------------------------ confirmation dialogs */
  function initConfirmations() {
    document.querySelectorAll("[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        var message = el.getAttribute("data-confirm") || "Are you sure?";
        if (!window.confirm(message)) {
          event.preventDefault();
        }
      });
    });
  }

  /* ------------------------------------- filter dropdowns auto-submit */
  function initAutoSubmitFilters() {
    document.querySelectorAll("form[data-autosubmit] select").forEach(function (select) {
      select.addEventListener("change", function () {
        select.form.submit();
      });
    });
  }

  /* -------------------------------------------------- file input label */
  function initFileInputs() {
    document.querySelectorAll("input[type=file]").forEach(function (input) {
      input.addEventListener("change", function () {
        var hint = input.parentElement.querySelector(".form-hint");
        if (!hint) {
          hint = document.createElement("small");
          hint.className = "form-hint";
          input.parentElement.appendChild(hint);
        }
        hint.textContent = input.files.length
          ? "Selected: " + input.files[0].name
          : "";
      });
    });
  }

  /* ------------------------------------------------------------- print */
  function initPrint() {
    document.querySelectorAll("[data-print]").forEach(function (button) {
      button.addEventListener("click", function () {
        window.print();
      });
    });
  }

  /* -------------------------------------------------- form double-submit */
  function initSubmitGuards() {
    document.querySelectorAll("form[method=post]").forEach(function (form) {
      form.addEventListener("submit", function () {
        var button = form.querySelector("button[type=submit]");
        if (button) {
          window.setTimeout(function () { button.disabled = true; }, 0);
          window.setTimeout(function () { button.disabled = false; }, 8000);
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSidebar();
    initAlerts();
    initConfirmations();
    initAutoSubmitFilters();
    initFileInputs();
    initPrint();
    initSubmitGuards();
  });
})();
