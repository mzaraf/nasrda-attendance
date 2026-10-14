const KEY = "nasrda-attendance-device-token";

export function deviceToken() {
  let value = localStorage.getItem(KEY);
  if (!value) {
    value = crypto.randomUUID ? crypto.randomUUID() + crypto.randomUUID() : `${Date.now()}-${Math.random()}-${Math.random()}`;
    localStorage.setItem(KEY, value);
  }
  return value;
}

export function deviceLabel() {
  return `${navigator.platform || "Browser"} browser`;
}
