// src/utils/auth.js

export const setToken = (token) => {
  if (token) {
    localStorage.setItem("access_token", token);
  } else {
    localStorage.removeItem("access_token");
  }
  // Dispatch a custom event to notify other parts of the app that the token has changed.
  window.dispatchEvent(new Event("token-change"));
};

export const getToken = () => {
  return localStorage.getItem("access_token");
};

export const removeToken = () => {
  localStorage.removeItem("access_token");
  // Dispatch the event on removal as well.
  window.dispatchEvent(new Event("token-change"));
};

// Alias for clarity in logout functions
export const clearToken = removeToken;
