import React, { useState, useEffect, useRef } from "react";

function Chat() {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hello! How can I help you today?", timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const chatEndRef = useRef(null);

  // Auto scroll to bottom on new message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Send message to backend
  const sendMessage = async () => {
    if (!input.trim()) return;

    setLoading(true);
    setError(null);

    // Add user's message locally
    const userMessage = { sender: "user", text: input.trim(), timestamp: new Date() };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });

      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }

      const data = await response.json();

      const aiMessage = {
        sender: "ai",
        text: data.response || "Sorry, I didn't get a response.",
        timestamp: new Date(),
      };
      setMessages((msgs) => [...msgs, aiMessage]);
    } catch (err) {
      setError("Failed to connect to backend. Please try again.");
      const errorMessage = {
        sender: "ai",
        text: "Oops! Something went wrong. Please try again later.",
        timestamp: new Date(),
      };
      setMessages((msgs) => [...msgs, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // Handle Enter key
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) {
        sendMessage();
      }
    }
  };

  // Format timestamps nicely
  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div
      style={{
        maxWidth: 600,
        margin: "2rem auto",
        padding: "1rem",
        borderRadius: 8,
        backgroundColor: "#121212",
        color: "white",
        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        boxShadow: "0 0 10px rgba(0,0,0,0.5)",
      }}
      aria-label="Nudge AI Chat Interface"
    >
      <h1 style={{ marginBottom: "1rem" }}>Nudge AI Chat</h1>

      <div
        style={{
          height: 400,
          overflowY: "auto",
          border: "1px solid #333",
          borderRadius: 8,
          padding: "1rem",
          backgroundColor: "#1e1e1e",
          marginBottom: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
        }}
        role="log"
        aria-live="polite"
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
              backgroundColor: msg.sender === "user" ? "#0b84ff" : "#333",
              color: "white",
              padding: "0.5rem 1rem",
              borderRadius: 12,
              maxWidth: "80%",
              wordBreak: "break-word",
              boxShadow: "0 2px 5px rgba(0,0,0,0.3)",
              position: "relative",
            }}
          >
            <div style={{ fontWeight: "bold", fontSize: "0.85rem", marginBottom: 2 }}>
              {msg.sender === "user" ? "You" : "Nudge AI"}
            </div>
            <div>{msg.text}</div>
            <time
              style={{
                fontSize: "0.7rem",
                color: "#bbb",
                position: "absolute",
                bottom: 4,
                right: 10,
              }}
              dateTime={msg.timestamp.toISOString()}
            >
              {formatTime(msg.timestamp)}
            </time>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {error && (
        <div
          role="alert"
          style={{
            marginBottom: "1rem",
            padding: "0.5rem",
            backgroundColor: "#b00020",
            color: "white",
            borderRadius: 4,
          }}
        >
          {error}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading && input.trim()) sendMessage();
        }}
        style={{ display: "flex", gap: "0.5rem" }}
        aria-label="Send a message"
      >
        <textarea
          aria-label="Message input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="Type your message here..."
          rows={2}
          style={{
            flexGrow: 1,
            resize: "none",
            padding: "0.5rem",
            borderRadius: 8,
            border: "1px solid #555",
            backgroundColor: "#222",
            color: "white",
            fontSize: "1rem",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            backgroundColor: "#0b84ff",
            border: "none",
            color: "white",
            padding: "0 1rem",
            borderRadius: 8,
            cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontWeight: "bold",
            fontSize: "1rem",
          }}
          aria-busy={loading}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}

export default Chat;
