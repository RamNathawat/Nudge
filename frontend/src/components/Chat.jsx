import React, { useState, useEffect, useRef, useCallback } from "react";

function formatTimestamp(ts) {
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now - date;
  const oneDay = 24 * 60 * 60 * 1000;

  if (diffMs < oneDay && date.getDate() === now.getDate()) {
    return `Today at ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}`;
  } else if (diffMs < 2 * oneDay && date.getDate() === now.getDate() - 1) {
    return `Yesterday at ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}`;
  } else {
    return `${date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}, ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}`;
  }
}

const MessageItem = React.memo(({ msg, prevMessageTimestamp, formatReplyPreview, handleContextMenu, editingIndex, editValue, setEditValue, saveEdit, styles, index }) => {
  const showTimestamp = !prevMessageTimestamp || (new Date(msg.timestamp) - new Date(prevMessageTimestamp)) / 60000 > 5;

  return (
    <>
      {showTimestamp && (
        <div style={styles.timestamp}>
          {formatTimestamp(msg.timestamp)}
        </div>
      )}
      <div style={styles.messageWrapper(msg.sender)}>
        <div>
          {msg.replyTo && (
            <div style={{ ...styles.replyPreview, textAlign: msg.sender === "user" ? "right" : "left" }}>
              {formatReplyPreview(msg.replyTo)}
            </div>
          )}
          {editingIndex === index ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: msg.sender === "user" ? "flex-end" : "flex-start" }}>
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                rows={3}
                style={{ ...styles.textArea, width: "auto", maxWidth: "65%", minWidth: "200px" }}
              />
              <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
                <button onClick={saveEdit} style={styles.sendButton}>Save</button>
                <button onClick={() => setEditValue("")} style={{ ...styles.sendButton, background: "#E0E0E0" }}>Cancel</button>
              </div>
            </div>
          ) : (
            <div style={styles.messageBubble(msg.sender)} onContextMenu={(e) => handleContextMenu(e, index)}>
              {msg.text}
            </div>
          )}
        </div>
      </div>
    </>
  );
});

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(() => localStorage.getItem("nudge_session_id"));
  const [safeMode, setSafeMode] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, messageIndex: null });
  const [editingIndex, setEditingIndex] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [replyToIndex, setReplyToIndex] = useState(null);

  const limit = 20;
  const chatEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const inputRef = useRef(null);
  const baseUrl = import.meta.env.VITE_API_URL;
  const initialLoadScrolled = useRef(false);
  const removeTraitsRegex = /\(Traits: \{[^}]+\}\)/g;

  const normalizeSender = useCallback((sender) => (!sender ? "ai" : sender.toLowerCase() === "user" ? "user" : "ai"), []);

  const fetchMessages = useCallback(async (currentOffset, isInitial = false) => {
    if (isFetchingMore || (!hasMore && !isInitial)) return;
    if (!isInitial) setIsFetchingMore(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${baseUrl}/memory?offset=${currentOffset}&limit=${limit}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const responseBody = await res.json();
      const fetchedMessages = responseBody.messages || [];
      const hasMoreFromBackend = responseBody.hasMore;
      const prevScrollHeight = messagesContainerRef.current ? messagesContainerRef.current.scrollHeight : 0;

      setMessages((m) => {
        const fetchedNormalized = fetchedMessages.map((e) => ({
          id: e._id,
          sender: normalizeSender(e.sender),
          text: e.content.replace(removeTraitsRegex, "").trim(),
          timestamp: e.timestamp || new Date(),
          replyTo: e.reply_to_id,
        }));
        const existingMessageIds = new Set(m.map(msg => msg.id).filter(id => id !== null));
        const uniqueFetched = fetchedNormalized.filter(msg => !existingMessageIds.has(msg.id));
        return isInitial ? uniqueFetched.reverse() : [...uniqueFetched.reverse(), ...m];
      });

      setOffset((prev) => prev + fetchedMessages.length);
      setHasMore(hasMoreFromBackend);

      if (!isInitial && messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight - prevScrollHeight;
      }
    } catch (err) {
      console.warn("Failed to fetch memory:", err);
    } finally {
      if (!isInitial) setIsFetchingMore(false);
    }
  }, [isFetchingMore, hasMore, baseUrl, limit, removeTraitsRegex, normalizeSender]);

  useEffect(() => {
    if (messages.length === 0 && hasMore && !isFetchingMore) fetchMessages(0, true);
  }, [fetchMessages, messages.length, hasMore, isFetchingMore]);

  useEffect(() => {
    if (chatEndRef.current && messagesContainerRef.current) {
      const container = messagesContainerRef.current;
      const scrollThreshold = 20;
      if (!initialLoadScrolled.current && messages.length > 0) {
        chatEndRef.current.scrollIntoView({ behavior: "instant" });
        initialLoadScrolled.current = true;
      } else if (container.scrollHeight - container.clientHeight - container.scrollTop < scrollThreshold && !isFetchingMore) {
        chatEndRef.current.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isFetchingMore]);

  useEffect(() => { if (!loading) inputRef.current?.focus(); }, [loading]);

  useEffect(() => {
    const handleClick = () => setContextMenu((m) => ({ ...m, visible: false }));
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      if (container.scrollTop < 50 && hasMore && !isFetchingMore) fetchMessages(offset);
    };
    let timeout;
    const debouncedScroll = () => {
      clearTimeout(timeout);
      timeout = setTimeout(handleScroll, 100);
    };
    container.addEventListener("scroll", debouncedScroll);
    return () => {
      container.removeEventListener("scroll", debouncedScroll);
      clearTimeout(timeout);
    };
  }, [offset, hasMore, isFetchingMore, fetchMessages]);

  const handleContextMenuCallback = useCallback((e, index) => {
    e.preventDefault();
    setContextMenu((m) => ({ ...m, visible: true, x: e.pageX, y: e.pageY, messageIndex: index }));
  }, []);

  const handleReply = useCallback(() => {
    setReplyToIndex(contextMenu.messageIndex);
    setContextMenu((m) => ({ ...m, visible: false }));
  }, [contextMenu.messageIndex]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(messages[contextMenu.messageIndex].text);
    setContextMenu((m) => ({ ...m, visible: false }));
  }, [messages, contextMenu.messageIndex]);

  const handleDelete = useCallback(async () => {
    const idx = contextMenu.messageIndex;
    const msg = messages[idx];
    const newMsgs = [...messages];
    newMsgs.splice(idx, 1);
    if (msg.sender === "user" && messages[idx + 1]?.sender === "ai") newMsgs.splice(idx, 1);
    setMessages(newMsgs);
    setContextMenu((m) => ({ ...m, visible: false }));

    if (msg.id) {
      try {
        const token = localStorage.getItem("access_token");
        await fetch(`${baseUrl}/memory/${msg.id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        setOffset(0);
        setHasMore(true);
        fetchMessages(0, true);
      } catch (e) {
        console.warn("Delete failed:", e);
      }
    }
  }, [messages, contextMenu.messageIndex, baseUrl, fetchMessages]);

  const handleEdit = useCallback(() => {
    const idx = contextMenu.messageIndex;
    setEditingIndex(idx);
    setEditValue(messages[idx].text);
    setContextMenu((m) => ({ ...m, visible: false }));
  }, [messages, contextMenu.messageIndex]);

  const formatReplyPreview = useCallback((id) => {
    const msg = messages.find((m) => m.id === id);
    const preview = msg ? msg.text.replace(removeTraitsRegex, '').trim() : '';
    return msg ? `Replying to: "${preview.slice(0, 60)}${preview.length > 60 ? "..." : ""}"` : null;
  }, [messages, removeTraitsRegex]);

  async function saveEdit() {
    const idx = editingIndex;
    const oldMessage = messages[idx];
    setEditingIndex(null);
    setEditValue("");
    const updatedContent = editValue.replace(removeTraitsRegex, '').trim();
    const updatedMsg = { ...oldMessage, text: updatedContent };
    setMessages((m) => m.map((msg, i) => (i === idx ? updatedMsg : msg)));

    if (oldMessage.id) {
      try {
        const token = localStorage.getItem("access_token");
        await fetch(`${baseUrl}/memory/${oldMessage.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ content: updatedContent }),
        });
      } catch (e) {
        console.warn("Edit backend failed:", e);
      }
    }
  }

  async function sendMessage() {
    if (!input.trim()) return;
    const now = new Date();
    const tempUserId = `temp-user-${Date.now()}`;
    const tempAiId = `temp-ai-${Date.now()}`;
    const userMsg = {
      id: tempUserId,
      sender: "user",
      text: input.trim(),
      timestamp: now,
      replyTo: replyToIndex !== null ? messages[replyToIndex]?.id : null,
    };
    setMessages((m) => [...m, userMsg, { id: tempAiId, sender: "ai", text: "typing...", timestamp: now }]);
    setInput("");
    setLoading(true);
    setReplyToIndex(null);
    setError(null);

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${baseUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: userMsg.text, ...(sessionId && { session_id: sessionId }), safe_mode: safeMode, reply_to_id: userMsg.replyTo }),
      });
      const data = await res.json();
      const cleanedResponse = data.response.replace(removeTraitsRegex, '').trim();

      setMessages((m) => {
        const updatedMsgs = m.map((msg) => (msg.id === tempUserId && data.user_message_id ? { ...msg, id: data.user_message_id } : msg));
        const aiMsgId = data.ai_message_id || `ai-${Date.now()}`;
        return [...updatedMsgs.slice(0, -1), { id: aiMsgId, sender: "ai", text: cleanedResponse, timestamp: new Date(), replyTo: userMsg.id }];
      });
    } catch (e) {
      console.error(e);
      setError("⚠️ Connection issue.");
      setMessages((m) => [...m.slice(0, -1), { id: null, sender: "ai", text: "Sorry, try again later.", timestamp: new Date() }]);
    } finally {
      setLoading(false);
    }
  }

  // New handler for Enter key press
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault(); // Prevent default newline behavior
      if (!loading && input.trim()) {
        sendMessage();
      }
    }
  };

  const styles = {
    appContainer: { height: "100vh", width: "100vw", display: "flex", flexDirection: "column", fontFamily: "'Inter', sans-serif", background: "#FFFDF5", color: "#2E2E2E", overflow: "hidden" },
    messagesContainer: { flexGrow: 1, overflowY: "auto", padding: "1.5rem 8% 7.5rem", backgroundColor: "#ffffff", display: "flex", flexDirection: "column", gap: "0.75rem" },
    messageWrapper: (s) => ({ display: "flex", justifyContent: s === "user" ? "flex-end" : "flex-start" }),
    messageBubble: (s) => ({ backgroundColor: s === "user" ? "#FFF59D" : "#FFE082", color: "#212121", padding: "1rem 1.5rem", borderRadius: s === "user" ? "20px 20px 5px 20px" : "20px 20px 20px 5px", maxWidth: "65%", whiteSpace: "pre-wrap", cursor: "context-menu", boxShadow: "0 2px 6px rgba(0,0,0,0.08)" }),
    timestamp: { textAlign: "center", fontSize: "0.8rem", color: "#6D4C41", margin: "1.5rem 0 0.8rem" },
    inputForm: { position: "fixed", bottom: 0, width: "100%", display: "flex", flexDirection: "column", gap: "0.5rem", padding: "1rem 0 1.5rem 0", background: "#FFFDE7", borderTop: "1px solid #F5F5F5", alignItems: "center" },
    inputContainer: { display: "flex", gap: "1rem", width: "90%", maxWidth: "800px" },
    textArea: { flexGrow: 1, padding: "0.8rem 1.2rem", borderRadius: "25px", border: "1px solid #BDBDBD", resize: "none", maxHeight: "100px", color: "#212121", backgroundColor: "#FFFFFF" },
    sendButton: { border: "none", background: "linear-gradient(45deg,#FFD54F,#FFC107)", color: "#212121", padding: "0.8rem 1.8rem", borderRadius: "25px", cursor: "pointer" },
    contextMenu: { position: "absolute", background: "#fff", border: "1px solid #E0E0E0", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 9999, color: "#212121" },
    contextItem: { padding: "0.6rem 1.5rem", cursor: "pointer", color: "#212121" },
    errorBox: { backgroundColor: "#FFEBEE", color: "#C62828", padding: "0.8rem 1.5rem", margin: "0.5rem 8% 0", borderRadius: "8px", textAlign: "center" },
    replyPreview: { fontSize: "0.75rem", color: "#757575", marginBottom: "0.25rem", textAlign: "left", paddingLeft: "1.5rem", paddingRight: "1.5rem" },
    replyIndicator: { backgroundColor: "#E0E0E0", borderRadius: "10px", padding: "0.5rem 1rem", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.9rem", color: "#424242", width: "90%", maxWidth: "800px", boxSizing: "border-box", margin: "0 auto" },
    replyIndicatorText: { flexGrow: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginRight: "0.5rem" },
    replyIndicatorClose: { background: "none", border: "none", fontSize: "1.2rem", cursor: "pointer", color: "#616161", padding: "0 0.3rem" },
    loadingMoreIndicator: { textAlign: 'center', padding: '0.5rem', color: '#757575', fontSize: '0.9rem' }
  };

  return (
    <div style={styles.appContainer}>
      <div ref={messagesContainerRef} style={styles.messagesContainer}>
        {isFetchingMore && <div style={styles.loadingMoreIndicator}>Loading older messages...</div>}
        {!isFetchingMore && messages.length === 0 && !hasMore && <p style={{ textAlign: 'center', padding: '1rem', color: '#555' }}>Hey! 😊 I'm Nudge. What's on your mind?</p>}
        {messages.map((msg, i) => (
          <MessageItem key={msg.id || `${msg.timestamp}-${i}`} msg={msg} index={i} prevMessageTimestamp={i > 0 ? messages[i - 1].timestamp : null} formatReplyPreview={formatReplyPreview} handleContextMenu={handleContextMenuCallback} editingIndex={editingIndex} editValue={editValue} setEditValue={setEditValue} saveEdit={saveEdit} styles={styles} />
        ))}
        <div ref={chatEndRef} />
      </div>

      {contextMenu.visible && (
        <div style={{ ...styles.contextMenu, top: contextMenu.y, left: contextMenu.x }}>
          <div onClick={handleEdit} style={styles.contextItem}>✏️ Edit</div>
          <div onClick={handleDelete} style={styles.contextItem}>🗑️ Delete</div>
          <div onClick={handleCopy} style={styles.contextItem}>📋 Copy</div>
          <div onClick={handleReply} style={styles.contextItem}>↩️ Reply</div>
        </div>
      )}

      {error && <div style={styles.errorBox}>{error}</div>}

      <form onSubmit={(e) => { e.preventDefault(); if (!loading && input.trim()) sendMessage(); }} style={styles.inputForm}>
        {replyToIndex !== null && messages[replyToIndex] && (
          <div style={styles.replyIndicator}>
            <span style={styles.replyIndicatorText}>
              Replying to: "{messages[replyToIndex].text.slice(0, 50)}{messages[replyToIndex].text.length > 50 ? "..." : ""}"
            </span>
            <button type="button" onClick={() => setReplyToIndex(null)} style={styles.replyIndicatorClose}>&times;</button>
          </div>
        )}
        <div style={styles.inputContainer}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown} 
            rows={1}
            style={styles.textArea}
            placeholder="Type your message..."
          />
          <button type="submit" disabled={loading || !input.trim()} style={styles.sendButton}>{loading ? "..." : "Send"}</button>
        </div>
      </form>
    </div>
  );
}

export default Chat;