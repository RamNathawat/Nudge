export function setToken(token) {
  localStorage.setItem("nudge_token", token);
}

export function getToken() {
  return localStorage.getItem("nudge_token");
}

export function removeToken() {
  localStorage.removeItem("nudge_token");
}
