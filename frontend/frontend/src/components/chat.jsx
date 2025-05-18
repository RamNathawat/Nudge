import React, { useState, useEffect, useRef } from "react";


function Chat() {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hey! 😊 I'm Nudge. What's on your mind?", timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);

    const userMessage = { sender: "user", text: input.trim(), timestamp: new Date() };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });

      if (!response.ok) throw new Error(`Status: ${response.status}`);
      const data = await response.json();

      const aiMessage = {
        sender: "ai",
        text: data.response || "Hmm... I didn’t catch that! Try again?",
        timestamp: new Date(),
      };
      setMessages((msgs) => [...msgs, aiMessage]);
    } catch (err) {
      setError("Couldn’t reach the server 😢");
      setMessages((msgs) => [
        ...msgs,
        {
          sender: "ai",
          text: "Oops! Something went wrong. Please try again later.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) sendMessage();
    }
  };

  const formatTime = (date) =>
    date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  


  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        backgroundColor: "#fffaf0",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "1rem",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 800,
          height: "100%",
          maxHeight: "100vh",
          backgroundColor: "#ffffff",
          borderRadius: "24px",
          padding: "2rem",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 0 40px rgba(0,0,0,0.1)",
          overflow: "hidden",
        }}
      >
        <h1
          style={{
            textAlign: "center",
            marginBottom: "1rem",
            color: "#d97706",
            fontSize: "2rem",
          }}
        >
          🧠 Nudge — Your Motivational AI Buddy
        </h1>

        <div
          style={{
            flexGrow: 1,
            overflowY: "auto",
            padding: "1rem",
            border: "1px solid #fcd34d",
            borderRadius: 16,
            backgroundColor: "#fff8e1",
            marginBottom: "1rem",
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
          }}
        >
          {messages.map((msg, i) => (
            <div
              key={i}
              style={{
                alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
                backgroundColor: msg.sender === "user" ? "#fde047" : "#fef3c7",
                color: "#1a202c",
                padding: "0.75rem 1rem",
                borderRadius: "16px",
                maxWidth: "80%",
                wordBreak: "break-word",
                boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
                position: "relative",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: 4 }}>
                {msg.sender === "user" ? "You" : "Nudge"}
              </div>
              <div>{msg.text}</div>
              <time
                style={{
                  fontSize: "0.7rem",
                  color: "#777",
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
              padding: "0.75rem",
              backgroundColor: "#fee2e2",
              color: "#b91c1c",
              borderRadius: 8,
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
          style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}
        >
          <textarea
            aria-label="Type your message"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            placeholder="Type something friendly..."
            rows={2}
            style={{
              flexGrow: 1,
              resize: "none",
              padding: "0.75rem",
              borderRadius: 12,
              border: "1px solid #fcd34d",
              backgroundColor: "#fff",
              color: "#333",
              fontSize: "1rem",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            style={{
              backgroundColor: "#fbbf24",
              border: "none",
              color: "#1f2937",
              padding: "0.6rem 1.2rem",
              borderRadius: 12,
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
              fontWeight: "bold",
              fontSize: "1rem",
              boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
              transition: "all 0.2s",
            }}
          >
            {loading ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Chat;
