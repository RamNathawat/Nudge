import React, { useState, useEffect, useRef } from "react";

function Chat() {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hey! 😊 I'm Nudge. What's on your mind?", timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem("nudge_session_id") || null;
  });
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading, messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);

    const userMessage = { sender: "user", text: input.trim(), timestamp: new Date() };
    setMessages((msgs) => [...msgs, userMessage]);
    setInput("");

    try {
      const requestBody = {
        message: userMessage.text,
        ...(sessionId && { session_id: sessionId }),
      };

      const baseUrl =
        window.location.hostname === "localhost"
          ? "http://localhost:8000"
          : "https://nudge-z04u.onrender.com";

      const response = await fetch(`${baseUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorDetails = await response.text();
        console.error("Server error details:", errorDetails);
        throw new Error(`Nudge backend error: ${response.status}`);
      }

      const data = await response.json();

      if (data.session_id) {
        setSessionId(data.session_id);
        localStorage.setItem("nudge_session_id", data.session_id);
      }

      const aiMessage = {
        sender: "ai",
        text: data.response || "Hmm... I didn’t catch that! Try again?",
        timestamp: new Date(),
      };
      setMessages((msgs) => [...msgs, aiMessage]);
    } catch (err) {
      setError("Oops! Nudge is having a moment. Please check your connection or try again.");
      console.error("Fetch error:", err);
      setMessages((msgs) => [
        ...msgs,
        {
          sender: "ai",
          text: "I'm sorry, I couldn't connect right now. Please try again later.",
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

  const styles = {
    // your original styles...
    appContainer: {
      height: "100vh",
      width: "100vw",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      fontFamily: "'Inter', sans-serif",
      fontSize: "16px",
      color: "#333333",
      background: "#F0F0E0",
      overflow: "hidden",
    },
    messagesContainer: {
      flexGrow: 1,
      overflowY: "auto",
      width: "100%",
      padding: "2rem 10% 6.5rem",
      backgroundColor: "#FFFFFF",
      display: "flex",
      flexDirection: "column",
    },
    messageWrapper: (sender) => ({
      width: "100%",
      display: "flex",
      justifyContent: sender === "user" ? "flex-end" : "flex-start",
      padding: "0.6rem 0",
    }),
    messageBubble: (sender) => ({
      backgroundColor: sender === "user" ? "#FFEFC4" : "#F8F0E0",
      color: "#333333",
      padding: "1.4rem 2rem",
      borderRadius: sender === "user" ? "25px 25px 8px 25px" : "25px 25px 25px 8px",
      maxWidth: "50%",
      wordBreak: "break-word",
      boxShadow: "0 3px 10px rgba(0,0,0,0.08)",
      fontSize: "1.15rem",
      lineHeight: 1.6,
    }),
    senderName: {
      fontWeight: 600,
      fontSize: "0.95rem",
      marginBottom: "0.6rem",
      color: "#8C7A6B",
    },
    messageTime: {
      fontSize: "0.8rem",
      color: "#B0A090",
      marginTop: "0.5rem",
    },
    inputForm: {
      position: "fixed",
      bottom: 0,
      width: "100%",
      display: "flex",
      gap: "1.2rem",
      alignItems: "center",
      padding: "1rem 10% 1.5rem",
      background: "#F0F0E0",
      zIndex: 100,
    },
    textArea: {
      flexGrow: 1,
      resize: "none",
      padding: "1.2rem 1.8rem",
      borderRadius: "22px",
      border: "1px solid #D8D8D8",
      backgroundColor: "#FFFFFF",
      color: "#333333",
      fontSize: "1.1rem",
      outline: "none",
    },
    sendButton: {
      border: "none",
      background: "linear-gradient(45deg, #FFD700, #FFC107)",
      color: "#333333",
      padding: "1.2rem 2.2rem",
      borderRadius: "22px",
      fontWeight: "bold",
      fontSize: "1.1rem",
      cursor: "pointer",
    },
    errorBox: {
      backgroundColor: "#FFEBEE",
      color: "#D32F2F",
      padding: "1rem",
      margin: "1rem auto",
      borderRadius: "10px",
      textAlign: "center",
    },
  };

  return (
    <div style={styles.appContainer}>
      <div style={styles.messagesContainer}>
        {messages.map((msg, i) => (
          <div key={i} style={styles.messageWrapper(msg.sender)}>
            <div style={styles.messageBubble(msg.sender)}>
              <div style={styles.senderName}>{msg.sender === "user" ? "YOU" : "NUDGE"}</div>
              <div>{msg.text}</div>
              <div style={styles.messageTime}>{formatTime(msg.timestamp)}</div>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading && input.trim()) sendMessage();
        }}
        style={styles.inputForm}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={loading ? "Sending..." : "Type your message here..."}
          rows={2}
          style={styles.textArea}
        />
        <button type="submit" disabled={loading || !input.trim()} style={styles.sendButton}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}

export default Chat;
