// src/App.jsx

import React, { useState, useEffect } from "react";
import Chat from "./components/chat"; // ✅ Correct casing
import Login from "./components/Login";
import Signup from "./components/Signup";
import { getToken, removeToken } from "./utils/auth";

function useDebugAuth(isAuthenticated) {
  useEffect(() => {
    console.log("[Debug] isAuthenticated changed:", isAuthenticated);
    console.log("[Debug] Current access_token:", localStorage.getItem("access_token"));
  }, [isAuthenticated]);
}

function App() {
  const [mode, setMode] = useState("login");
  const [isAuthenticated, setIsAuthenticated] = useState(!!getToken());

  useDebugAuth(isAuthenticated);

  useEffect(() => {
    console.log("[Debug] App mounted");
    console.log("[Debug] Token on mount:", getToken());

    const handleTokenChange = () => {
      const token = getToken();
      console.log("[Debug] Token change detected:", token);
      setIsAuthenticated(!!token);
    };

    window.addEventListener("token-change", handleTokenChange);
    return () => window.removeEventListener("token-change", handleTokenChange);
  }, []);

  const handleLogout = () => {
    console.log("[Debug] Logging out");
    removeToken();
  };

  const handleLogin = () => {
    console.log("[Debug] Login handler called");
    // No need to set state manually — token-change event handles it
  };

  return (
    <div>
      {isAuthenticated ? (
        <>
          <button onClick={handleLogout}>Logout</button>
          <Chat />
        </>
      ) : mode === "login" ? (
        <>
          <Login onLogin={handleLogin} />
          <button onClick={() => setMode("signup")}>Go to Signup</button>
        </>
      ) : (
        <>
          <Signup onSwitch={() => setMode("login")} />
          <button onClick={() => setMode("login")}>Go to Login</button>
        </>
      )}
    </div>
  );
}

export default App;