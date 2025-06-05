import React, { useState } from "react";

function Signup({ onSwitch }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const signup = async (e) => {
    e.preventDefault();
    const res = await fetch(`${import.meta.env.VITE_API_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) {
      alert("Account created! Please log in.");
      onSwitch();
    } else {
      const data = await res.json();
      alert(data.detail || "Signup failed");
    }
  };

  return (
    <form onSubmit={signup}>
      <h2>Sign Up</h2>
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Create Account</button>
    </form>
  );
}

export default Signup;
