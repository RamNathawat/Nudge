import React, { useState } from "react";
import { setToken } from "../utils/auth";

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const login = async (e) => {
    e.preventDefault();
    setError("");
    console.log("[Debug] Login attempt:", { email, password: "****" });

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        }
      );

      console.log("[Debug] Response status:", response.status);

      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        throw new Error("Invalid server response.");
      }

      console.log("[Debug] Response data:", data);

      if (!response.ok) {
        throw new Error(data.detail || "Invalid login credentials.");
      }

      if (data.access_token) {
        console.log("[Debug] Login success — token set.");
        setToken(data.access_token);
        onLogin(); // this will trigger token-change listener
      } else {
        throw new Error("Login failed. Please try again.");
      }
    } catch (err) {
      console.error("[Debug] Login error:", err.message);
      setError(err.message || "Something went wrong.");
    }
  };

  return (
    <form
      onSubmit={login}
      style={{ maxWidth: "400px", margin: "auto", padding: "2rem" }}
    >
      <h2>Login to Nudge</h2>

      {error && (
        <div style={{ color: "red", marginBottom: "1rem" }}>{error}</div>
      )}

      <input
        placeholder="Email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={{
          width: "100%",
          marginBottom: "1rem",
          padding: "0.8rem",
        }}
      />

      <input
        placeholder="Password"
        type="password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={{
          width: "100%",
          marginBottom: "1.5rem",
          padding: "0.8rem",
        }}
      />

      <button
        type="submit"
        style={{ padding: "0.8rem 1.5rem", width: "100%" }}
      >
        Log In
      </button>
    </form>
  );
}

export default Login;