import React, { useState } from "react";
import Chat from "./components/Chat"; // Ensure consistent casing for Chat.jsx/Chat.js
import Login from "./components/login";
import Signup from "./components/Signup";
import { getToken, removeToken } from "./utils/auth"; // Assuming these utilities exist

function App() {
  // State to manage the current mode: 'login' or 'signup'
  const [mode, setMode] = useState("login");

  // Check if a token exists to determine if the user is authenticated
  const isAuthenticated = !!getToken();

  // Handler for the logout action
  const handleLogout = () => {
    removeToken(); // Remove the authentication token
    window.location.reload(); // Reload the page to reset the application state
  };

  return (
    <div>
      {isAuthenticated ? (
        // If the user is authenticated, display the Logout button and the Chat component
        <>
          <button onClick={handleLogout}>Logout</button>
          <Chat />
        </>
      ) : mode === "login" ? (
        // If not authenticated and in 'login' mode, display the Login component
        // and a button to switch to 'signup' mode
        <>
          <Login onLogin={() => window.location.reload()} />
          <button onClick={() => setMode("signup")}>Go to Signup</button>
        </>
      ) : (
        // If not authenticated and in 'signup' mode, display the Signup component
        // and a button to switch back to 'login' mode
        <>
          <Signup onSwitch={() => setMode("login")} />
          <button onClick={() => setMode("login")}>Go to Login</button>
        </>
      )}
    </div>
  );
}

export default App; // Export the single, correct App component as the default export