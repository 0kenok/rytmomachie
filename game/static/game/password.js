// Show / hide toggle for password fields. The buttons are hidden in the HTML
// and only shown here, so nothing useless appears when JavaScript is off.
(function () {
  "use strict";
  document.querySelectorAll(".reveal-password").forEach((button) => {
    const input = document.getElementById(button.getAttribute("aria-controls"));
    if (!input) return;
    button.hidden = false;
    button.addEventListener("click", () => {
      const reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      const label = reveal ? button.dataset.hideLabel : button.dataset.showLabel;
      button.setAttribute("aria-pressed", String(reveal));
      button.setAttribute("aria-label", label);
      button.title = label;
      input.focus();
    });
  });
  // Never submit with the password left visible in the field.
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      form.querySelectorAll(".password-field input").forEach((input) => { input.type = "password"; });
    });
  });
})();
