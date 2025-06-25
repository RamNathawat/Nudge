import React, { useState } from "react";

function Signup({ onSwitch }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const signup = async (e) => {
    e.preventDefault();
    setError("");
    console.log("[Debug] Signup attempt with:", { email, password: "***" });

    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      console.log("[Debug] Signup response status:", res.status);

      if (res.ok) {
        alert("Account created! Please log in.");
        onSwitch();
      } else {
        const data = await res.json();
        const errorMsg = data.detail || "Signup failed";
        setError(errorMsg);
        alert(errorMsg);
        console.error("[Debug] Signup error:", errorMsg);
      }
    } catch (err) {
      setError(err.message);
      console.error("[Debug] Signup error:", err.message);
    }
  };

  return (
    <form onSubmit={signup} style={{ maxWidth: "400px", margin: "auto", padding: "2rem" }}>
      <h2>Sign Up</h2>
      {error && <div style={{ color: "red", marginBottom: "1rem" }}>{error}</div>}
      <input
        placeholder="Email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={{ width: "100%", marginBottom: "1rem", padding: "0.8rem" }}
      />
      <input
        placeholder="Password"
        type="password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={{ width: "100%", marginBottom: "1.5rem", padding: "0.8rem" }}
      />
      <button type="submit" style={{ padding: "0.8rem 1.5rem" }}>
        Create Account
      </button>
      <button
        type="button"
        onClick={onSwitch}
        style={{ marginLeft: "1rem", padding: "0.8rem 1.5rem" }}
      >
        Go to Login
      </button>
    </form>
  );
}

export default Signup;