// Small helpers for all pages; the pages work without them.

// Show points in time in the local time of the browser.
for (const element of document.querySelectorAll("time.local-time")) {
  const date = new Date(element.dateTime);
  if (!Number.isNaN(date.getTime())) {
    element.textContent = date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" });
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
