import React, { useState, useEffect, useRef } from "react";

function Chat() {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hey! 😊 I'm Nudge. What's on your mind?", timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const messagesContainerRef = useRef(null);

  // Scroll to latest message on new message
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Focus input when not loading or after messages update
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

      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorDetails = await response.text();
        console.error("Server error details:", errorDetails);
        throw new Error(`Nudge backend error: ${response.status}. Please check server logs.`);
      }

      const data = await response.json();

      if (data.session_id) {
        setSessionId(data.session_id);
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
          text: "I'm sorry, I couldn't connect right now. Please check your internet connection or try again later.",
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
    appContainer: {
      height: "100vh",
      width: "100vw",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      fontFamily: "'Inter', sans-serif",
      fontSize: "16px",
      color: "#333333",
      background: "#F0F0E0", // Slightly lighter, softer background for elegance
      overflow: "hidden",
    },
    // Header styles removed as the header element is removed
    messagesContainer: {
      flexGrow: 1,
      overflowY: "auto",
      width: "100%",
      // Adjusted padding-top as there's no fixed header now.
      // Keeping original padding for bottom for the input form.
      padding: "2rem 10% 6.5rem", // Default top padding, still accounting for input form
      backgroundColor: "#FFFFFF",
      borderRadius: "0",
      display: "flex",
      flexDirection: "column",
      boxShadow: "none",
      position: "relative",
      margin: "0",
      "&::before": {
        content: "''",
        position: "absolute",
        left: "50%",
        top: "0",
        bottom: "0",
        width: "1px",
        background: "linear-gradient(to bottom, #FFD70033, #FFC10733, transparent)",
        transform: "translateX(-50%)",
        zIndex: 0,
        borderRadius: "0.5px",
      },
      "&::-webkit-scrollbar": {
        width: "10px",
      },
      "&::-webkit-scrollbar-track": {
        background: "#F8F8F8",
        borderRadius: "10px",
      },
      "&::-webkit-scrollbar-thumb": {
        background: "linear-gradient(180deg, #FFD700, #FFC107)",
        borderRadius: "10px",
        border: "2px solid #FFFFFF",
      },
      "&::-webkit-scrollbar-thumb:hover": {
        background: "linear-gradient(180deg, #FFC107, #FF8C00)",
      },
    },
    messageWrapper: (sender) => ({
      width: "100%",
      display: "flex",
      justifyContent: sender === "user" ? "flex-end" : "flex-start",
      padding: "0.6rem 0",
      position: "relative",
      zIndex: 1,
      opacity: 0,
      transform: "translateY(20px)",
      animation: "fadeInUp 0.6s ease-out forwards",
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
      transition: "all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)",
      "&:hover": {
        transform: "translateY(-5px) scale(1.02)",
        boxShadow: "0 6px 15px rgba(0,0,0,0.12)",
      },
      marginRight: sender === "user" ? "calc(50% - 30%)" : "0",
      marginLeft: sender === "ai" ? "calc(50% - 30%)" : "0",
    }),
    senderName: {
      fontWeight: 600,
      fontSize: "0.95rem",
      marginBottom: "0.6rem",
      color: "#8C7A6B",
      textTransform: "uppercase",
      letterSpacing: "0.04em",
      opacity: 0.85,
    },
    messageTime: {
      fontSize: "0.8rem",
      color: "#B0A090",
      position: "absolute",
      bottom: "12px",
      right: "18px",
      opacity: 0.7,
      fontWeight: 300,
    },
    errorBox: {
      marginBottom: "2rem",
      padding: "1.5rem",
      backgroundColor: "#FFEBEE",
      color: "#D32F2F",
      borderRadius: "15px",
      textAlign: "center",
      fontWeight: 600,
      boxShadow: "0 3px 10px rgba(0,0,0,0.08)",
      border: "1px solid #FFD3D3",
      width: "auto",
      maxWidth: "600px",
      margin: "0 auto 2rem",
      zIndex: 3,
    },
    inputForm: {
      position: "fixed",
      bottom: 0,
      width: "100%",
      display: "flex",
      gap: "1.2rem",
      alignItems: "center",
      padding: "1rem 10% 1.5rem", // Padding for input form
      background: "#F0F0E0",
      zIndex: 100,
      boxShadow: "0 -2px 5px rgba(0,0,0,0.05)", // Slight shadow for bar effect
      justifyContent: "center",
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
      boxShadow: "inset 0 1px 3px rgba(0,0,0,0.08)",
      transition: "all 0.3s ease-in-out",
      "&:focus": {
        borderColor: "#FFD700",
        boxShadow: "0 0 0 3px rgba(255,215,0,0.25), inset 0 1px 3px rgba(0,0,0,0.1)",
        backgroundColor: "#FFFFFF",
      },
      "&::placeholder": {
        color: "#B0A090",
        opacity: 0.9,
        fontWeight: 300,
      }
    },
    sendButton: (loading, input) => ({
      border: "none",
      color: "#333333",
      padding: "1.2rem 2.2rem",
      borderRadius: "22px",
      cursor: loading || !input.trim() ? "not-allowed" : "pointer",
      fontWeight: "bold",
      fontSize: "1.1rem",
      boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
      transition: "all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)",
      opacity: loading || !input.trim() ? 0.5 : 1,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: "0.5rem",
      background: loading || !input.trim()
        ? "linear-gradient(45deg, #FFD700, #FFC107)"
        : "linear-gradient(45deg, #FFD700, #FFC107)",
      "&:hover": {
        transform: loading || !input.trim() ? "none" : "translateY(-3px)",
        boxShadow: "0 6px 15px rgba(0,0,0,0.2)",
        background: loading || !input.trim() ? undefined : "linear-gradient(45deg, #FFC107, #FF8C00)",
      },
      "&:active": {
        transform: "translateY(0px)",
        boxShadow: "0 3px 8px rgba(0,0,0,0.1)",
        background: "linear-gradient(45deg, #FFB300, #FFD700)",
      }
    }),
    sendButtonIcon: {
      fontSize: "1.2em",
      lineHeight: 1,
      textShadow: "none",
    },
    // Media queries for responsiveness
    "@media (max-width: 1024px)": {
      messagesContainer: {
        padding: "2rem 5% 6.5rem", // Adjusted for smaller screens
      },
      inputForm: {
        padding: "1rem 5% 1.5rem",
      },
    },
    "@media (max-width: 768px)": {
      messagesContainer: {
        padding: "1.5rem 4% 5.8rem", // Adjusted for tablets
      },
      messageBubble: {
        maxWidth: "70%",
        padding: "1rem 1.5rem",
        marginRight: (sender) => (sender === "user" ? "8%" : "0"),
        marginLeft: (sender) => (sender === "ai" ? "8%" : "0"),
        fontSize: "1.05rem",
      },
      senderName: {
        fontSize: "0.9rem",
      },
      messageTime: {
        fontSize: "0.75rem",
      },
      errorBox: {
        maxWidth: "85%",
        padding: "1rem",
        fontSize: "0.85rem",
      },
      inputForm: {
        padding: "0.8rem 4% 1rem",
        gap: "0.8rem",
      },
      textArea: {
        padding: "0.9rem 1.2rem",
        fontSize: "0.95rem",
      },
      sendButton: {
        padding: "0.9rem 1.6rem",
        fontSize: "1rem",
      },
    },
    "@media (max-width: 480px)": {
      messagesContainer: {
        padding: "1rem 2% 5rem", // Adjusted for mobile
      },
      messageBubble: {
        maxWidth: "90%",
        padding: "0.8rem 1.2rem",
        marginRight: (sender) => (sender === "user" ? "2%" : "0"),
        marginLeft: (sender) => (sender === "ai" ? "2%" : "0"),
        fontSize: "0.95rem",
      },
      errorBox: {
        padding: "0.8rem",
        fontSize: "0.8rem",
      },
      inputForm: {
        flexDirection: "column",
        gap: "0.6rem",
        padding: "0.6rem 2% 0.8rem",
      },
      textArea: {
        width: "100%",
        maxWidth: "100%",
        padding: "0.8rem 1rem",
        fontSize: "0.9rem",
        borderRadius: "20px",
      },
      sendButton: {
        width: "100%",
        padding: "0.8rem 1rem",
        fontSize: "0.9rem",
        borderRadius: "20px",
      },
    },
  };

  const globalStyles = `
    @keyframes fadeInUp {
      0% { opacity: 0; transform: translateY(20px); }
      100% { opacity: 1; transform: translateY(0); }
    }
  `;

  return (
    <div style={styles.appContainer}>
      <style>{globalStyles}</style>

      {/* Header removed */}

      {/* Messages Container */}
      <div style={styles.messagesContainer} ref={messagesContainerRef}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              ...styles.messageWrapper(msg.sender),
              animationDelay: `${i * 0.05}s`,
            }}
          >
            <div style={styles.messageBubble(msg.sender)}>
              <div style={styles.senderName}>
                {msg.sender === "user" ? "YOU" : "NUDGE"}
              </div>
              <div>{msg.text}</div>
              <time
                style={styles.messageTime}
                dateTime={msg.timestamp.toISOString()}
              >
                {formatTime(msg.timestamp)}
              </time>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Error Box */}
      {error && (
        <div role="alert" style={styles.errorBox}>
          {error}
        </div>
      )}

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!loading && input.trim()) sendMessage();
        }}
        style={styles.inputForm}
      >
        <textarea
          ref={inputRef}
          aria-label={loading ? "Sending message" : "Type your message"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder={loading ? "Sending..." : "Type your message here..."}
          rows={2}
          style={styles.textArea}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={styles.sendButton(loading, input)}
        >
          {loading ? (
            <>
              <span style={styles.sendButtonIcon}>⏳</span> SENDING
            </>
          ) : (
            <>
              <span style={styles.sendButtonIcon}>➤</span> SEND
            </>
          )}
        </button>
      </form>
    </div>
  );
}

export default Chat;