// Small helpers for all pages; the pages work without them.

// Show points in time in the local time of the browser.
for (const element of document.querySelectorAll("time.local-time")) {
  const date = new Date(element.dateTime);
  if (!Number.isNaN(date.getTime())) {
    element.textContent =
      element.dataset.format === "time"
        ? date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })
        : date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
  }
}

// Ask before a form deletes something.
for (const form of document.querySelectorAll("form[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
}

// datetime-local inputs hold local time; the server gets UTC through a hidden field.
for (const input of document.querySelectorAll("input[data-utc-target]")) {
  const target = document.getElementById(input.dataset.utcTarget);
  if (target.value) {
    const date = new Date(target.value);
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    input.value = local.toISOString().slice(0, 16);
  }
  input.addEventListener("change", () => {
    target.value = input.value ? new Date(input.value).toISOString() : "";
  });
}

// A click into a link field selects the whole link, ready to copy.
for (const input of document.querySelectorAll("input.select-on-focus")) {
  input.addEventListener("focus", () => input.select());
}

// Gear form: show only the extra fields that belong to the chosen type.
for (const select of document.querySelectorAll('select[name="type_id"]')) {
  const groups = select.form.querySelectorAll(".kind-fields");
  const update = () => {
    const kind = select.selectedOptions[0] ? select.selectedOptions[0].dataset.kind : "";
    for (const group of groups) {
      group.hidden = group.dataset.kind !== kind;
      for (const input of group.querySelectorAll("input, select")) input.disabled = group.hidden;
    }
  };
  select.addEventListener("change", update);
  update();
}
