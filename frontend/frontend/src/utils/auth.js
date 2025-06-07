// src/utils/auth.js

export const setToken = (token) => {
  localStorage.setItem("access_token", token);
  window.dispatchEvent(new Event("token-change")); // Notify app of token update
};

export const getToken = () => {
  return localStorage.getItem("access_token");
};

export const clearToken = () => {
  localStorage.removeItem("access_token");
  window.dispatchEvent(new Event("token-change")); // Notify app of token removal
};

export const removeToken = clearToken; // Alias for logout usage
