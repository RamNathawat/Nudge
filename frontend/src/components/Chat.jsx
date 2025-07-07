import React, { useState, useEffect, useRef, useCallback } from "react";

// --- Helper Components & Icons ---

// Simple SVG Icon component for clarity
const Icon = ({ path, size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
    <path d={path} fill="currentColor" />
  </svg>
);

const PaperclipIcon = () => <Icon path="M16.5 6V17.5C16.5 20.2614 14.2614 22.5 11.5 22.5C8.73858 22.5 6.5 20.2614 6.5 17.5V5C6.5 3.61929 7.61929 2.5 9 2.5C10.3807 2.5 11.5 3.61929 11.5 5V15.5C11.5 16.0523 11.0523 16.5 10.5 16.5C9.94772 16.5 9.5 16.0523 9.5 15.5V6H8V15.5C8 16.8807 9.11929 18 10.5 18C11.8807 18 13 16.8807 13 15.5V5C13 2.79086 11.2091 1 9 1C6.79086 1 5 2.79086 5 5V17.5C5 21.0899 7.91015 24 11.5 24C15.0899 24 18 21.0899 18 17.5V6H16.5Z" />;
const SendIcon = () => <Icon path="M3.47827 2.32589L20.5217 9.32589C21.6934 9.81577 21.6934 11.1842 20.5217 11.6741L3.47827 18.6741C2.30663 19.164 1 18.2283 1 17L1 4C1 2.77169 2.30663 1.83598 3.47827 2.32589Z" />;
const NudgeLogo = () => (
    <div style={{ fontWeight: 'bold', fontSize: '24px', color: '#111', padding: '0 20px', display: 'flex', alignItems: 'center' }}>
        N<span style={{ color: '#FFD54F' }}>.</span>
    </div>
);

// --- Main Chat Component ---

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
      <div style={styles.messageRow(msg.sender)}>
        {msg.sender !== "user" && <div style={styles.avatar}></div>}
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
                <button onClick={saveEdit} style={styles.toolButton()}>Save</button>
                <button onClick={() => setEditValue("")} style={{ ...styles.toolButton(), background: "#E0E0E0" }}>Cancel</button>
              </div>
            </div>
          ) : (
            <div style={styles.bubble(msg.sender)} onContextMenu={(e) => handleContextMenu(e, index)}>
              {msg.text}
            </div>
          )}
        </div>
        {msg.sender === "user" && <div style={styles.avatar}></div>}
      </div>
    </>
  );
});

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [safeMode, setSafeMode] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [contextMenu, setContextMenu] = useState({ visible: false, x: 0, y: 0, messageIndex: null });
  const [editingIndex, setEditingIndex] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [replyToIndex, setReplyToIndex] = useState(null);
  const [activeTool, setActiveTool] = useState('chat');
  const [hoveredTool, setHoveredTool] = useState('');

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
    setIsFetchingMore(true);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${baseUrl}/memory?offset=${currentOffset}&limit=${limit}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const responseBody = await res.json();
      
      const fetchedMessages = responseBody?.memory?.messages || [];
      const hasMoreFromBackend = responseBody?.memory?.hasMore || false;

      const prevScrollHeight = messagesContainerRef.current ? messagesContainerRef.current.scrollHeight : 0;

      setMessages((m) => {
        const fetchedNormalized = fetchedMessages.map((e) => ({
          id: e._id,
          sender: normalizeSender(e.sender),
          text: (e.content || "").replace(removeTraitsRegex, "").trim(),
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
      setIsFetchingMore(false);
    }
  }, [isFetchingMore, hasMore, baseUrl, limit, removeTraitsRegex, normalizeSender]);

  useEffect(() => {
    if (messages.length === 0 && hasMore && !isFetchingMore) {
        fetchMessages(0, true);
    }
  }, [fetchMessages, messages.length, hasMore, isFetchingMore]);

  useEffect(() => {
    if (chatEndRef.current && messagesContainerRef.current) {
      const container = messagesContainerRef.current;
      if (!initialLoadScrolled.current && messages.length > 0) {
        chatEndRef.current.scrollIntoView({ behavior: "instant" });
        initialLoadScrolled.current = true;
      } else if (container.scrollHeight - container.clientHeight - container.scrollTop < 200 && !isFetchingMore) {
        chatEndRef.current.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isFetchingMore]);

  useEffect(() => { if (!loading) inputRef.current?.focus(); }, [loading, activeTool]);

  useEffect(() => {
    const handleClick = () => setContextMenu({ visible: false, x: 0, y: 0, messageIndex: null });
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
    setContextMenu({ visible: true, x: e.pageX, y: e.pageY, messageIndex: index });
  }, []);

  const handleReply = useCallback(() => {
    setReplyToIndex(contextMenu.messageIndex);
    setContextMenu({ visible: false });
  }, [contextMenu.messageIndex]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(messages[contextMenu.messageIndex].text);
    setContextMenu({ visible: false });
  }, [messages, contextMenu.messageIndex]);

  const handleDelete = useCallback(async () => {
    const idx = contextMenu.messageIndex;
    if (idx === null || !messages[idx]) return;
    const msgToDelete = messages[idx];
    setMessages(prev => prev.filter((_, i) => i !== idx));
    setContextMenu({ visible: false });

    if (msgToDelete.id) {
      try {
        const token = localStorage.getItem("access_token");
        await fetch(`${baseUrl}/memory/${msgToDelete.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      } catch (e) { console.warn("Delete failed:", e); }
    }
  }, [messages, contextMenu.messageIndex, baseUrl]);

  const handleEdit = useCallback(() => {
    const idx = contextMenu.messageIndex;
    setEditingIndex(idx);
    setEditValue(messages[idx].text);
    setContextMenu({ visible: false });
  }, [messages, contextMenu.messageIndex]);

  const formatReplyPreview = useCallback((id) => {
    const msg = messages.find((m) => m.id === id);
    const preview = msg?.text.replace(removeTraitsRegex, '').trim() || '';
    return msg ? `Replying to: "${preview.slice(0, 60)}${preview.length > 60 ? "..." : ""}"` : null;
  }, [messages, removeTraitsRegex]);

  const saveEdit = async () => {
    const idx = editingIndex;
    const oldMessage = messages[idx];
    setEditingIndex(null);
    const updatedContent = editValue.replace(removeTraitsRegex, '').trim();
    const updatedMsg = { ...oldMessage, text: updatedContent };
    setMessages((m) => m.map((msg, i) => (i === idx ? updatedMsg : msg)));
    setEditValue("");

    if (oldMessage.id) {
      try {
        const token = localStorage.getItem("access_token");
        await fetch(`${baseUrl}/memory/${oldMessage.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ content: updatedContent }),
        });
      } catch (e) { console.warn("Edit backend failed:", e); }
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim()) return;
    
    if (activeTool === 'chat') {
        await sendChatMessage();
    } else {
        await sendResearchQuery();
    }
  };

  const sendChatMessage = async () => {
    const userMsgText = input.trim();
    const tempAiId = `temp-ai-${Date.now()}`;
    const userMsg = {
      id: `temp-user-${Date.now()}`,
      sender: "user",
      text: userMsgText,
      timestamp: new Date(),
      replyTo: replyToIndex !== null ? messages[replyToIndex]?.id : null,
    };
    setMessages((m) => [...m, userMsg, { id: tempAiId, sender: "ai", text: "...", timestamp: new Date() }]);
    setInput("");
    setLoading(true);
    setReplyToIndex(null);
    setError(null);

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${baseUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: userMsg.text, reply_to_id: userMsg.replyTo }),
      });
      const data = await res.json();
      
      // *** THIS IS THE FIX ***
      // Safely handle cases where data.response might be missing or not a string
      const cleanedResponse = (data.response || "").replace(removeTraitsRegex, '').trim();

      setMessages((m) => m.map(msg => msg.id === tempAiId ? { ...msg, text: cleanedResponse, id: data.ai_message_id || `ai-${Date.now()}`} : msg));
    } catch (e) {
      console.error(e);
      setError("⚠️ Connection issue.");
      setMessages((m) => m.map(msg => msg.id === tempAiId ? { ...msg, text: "Sorry, try again later." } : msg));
    } finally {
      setLoading(false);
    }
  };

  const sendResearchQuery = async () => {
    const query = input.trim();
    const endpoint = activeTool === 'online_search' ? '/online_search' : '/deep_research';
    const tempAiId = `temp-ai-${Date.now()}`;
    const userMsg = {
        id: `temp-user-${Date.now()}`,
        sender: "user",
        text: `Researching: ${query}`,
        timestamp: new Date(),
    };
    setMessages((m) => [...m, userMsg, { id: tempAiId, sender: "ai", text: `Performing ${activeTool.replace(/_/g, ' ')}...`, timestamp: new Date() }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
        const token = localStorage.getItem("access_token");
        const res = await fetch(`${baseUrl}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ query }),
        });

        if (!res.ok) {
            let errorDetail = 'Research request failed';
            try {
                const errData = await res.json();
                errorDetail = errData.detail || errorDetail;
            } catch (jsonError) {
                errorDetail = await res.text();
            }
            throw new Error(errorDetail);
        }

        if (activeTool === 'deep_research') {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Nudge_Research_${query.slice(0, 20)}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            setMessages((m) => m.map(msg => msg.id === tempAiId ? { ...msg, text: `Deep research report for "${query}" has been downloaded.` } : msg));
        } else {
            const data = await res.json();
            const summary = `**Search Summary for "${query}"**:\n\n${data.explanation}\n\n**Sources:**\n${(data.references || []).slice(0, 3).join('\n')}`;
            setMessages((m) => m.map(msg => msg.id === tempAiId ? { ...msg, text: summary } : msg));
        }

    } catch (e) {
        console.error(e);
        setError(`⚠️ ${e.message}`);
        setMessages((m) => m.map(msg => msg.id === tempAiId ? { ...msg, text: `Failed to perform research. Please try again.` } : msg));
    } finally {
        setLoading(false);
        setActiveTool('chat');
    }
  };

  const toggleSafeMode = async () => {
    const newMode = !safeMode;
    try {
      const token = localStorage.getItem("access_token");
      await fetch(`${baseUrl}/safe-space-mode?enabled=${newMode}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      setSafeMode(newMode);
    } catch (err) { console.error("Safe mode toggle failed", err); }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) {
        handleSendMessage();
      }
    }
  };

  const getPlaceholderText = () => {
    switch(activeTool) {
        case 'online_search': return 'Enter a topic to search online...';
        case 'deep_research': return 'Enter a topic for a deep research report...';
        default: return 'Type your message...';
    }
  };

  const styles = {
    fontFamily: "'Satoshi', sans-serif",
    container: { display: "flex", height: "100vh", width: "100vw", background: "#F7F7F8", fontFamily: "'Satoshi', sans-serif" },
    sidebar: { width: "260px", background: "#FFFFFF", borderRight: "1px solid #EAEAEA", display: "flex", flexDirection: "column", padding: "10px 0" },
    sidebarHeader: { padding: "10px 0", marginBottom: '20px' },
    toolButton: (toolName) => ({ 
        background: activeTool === toolName ? '#FFFBEB' : (hoveredTool === toolName ? '#F7F7F8' : 'transparent'),
        border: 'none', 
        padding: '10px 20px', 
        width: '100%', 
        textAlign: 'left', 
        cursor: 'pointer', 
        fontSize: '15px', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '12px', 
        color: activeTool === toolName ? '#111' : '#555',
        borderRadius: '8px', 
        margin: '2px 0',
        fontWeight: activeTool === toolName ? '700' : '500',
        transition: 'background-color 0.2s, color 0.2s',
    }),
    sidebarSection: { padding: '0 10px', marginBottom: '20px' },
    sidebarTitle: { padding: '0 20px', fontSize: '12px', color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' },
    main: { flex: 1, display: "flex", flexDirection: "column", width: "100%", overflow: "hidden" },
    chat: { flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "10px" },
    messageRow: (sender) => ({ display: "flex", gap: "12px", alignItems: "flex-end", alignSelf: sender === "user" ? "flex-end" : "flex-start", justifyContent: sender === "user" ? "flex-end" : "flex-start", maxWidth: '85%' }),
    avatar: { height: "32px", width: "32px", borderRadius: "50%", backgroundColor: "#FFD54F", flexShrink: 0 },
    bubble: (sender) => ({ backgroundColor: sender === "user" ? "#FFD54F" : "#FFFFFF", color: "#111", padding: "10px 14px", borderRadius: "12px", maxWidth: "100%", wordBreak: "break-word", textTransform: "lowercase", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", lineHeight: '1.5' }),
    inputWrapper: { padding: '20px', background: '#F7F7F8' },
    inputContainer: { display: "flex", alignItems: "center", padding: "8px", border: "1px solid #EAEAEA", borderRadius: "16px", background: "#fff", boxShadow: '0 4px 12px rgba(0,0,0,0.05)' },
    textArea: { flex: 1, border: "none", padding: "10px", resize: "none", background: "transparent", color: "black", outline: "none", fontSize: '16px' },
    iconButton: { background: "none", border: "none", cursor: "pointer", color: '#888', padding: '8px' },
    sendButton: { background: "#FFD54F", border: "none", cursor: "pointer", borderRadius: "12px", width: "44px", height: "44px", display: "flex", alignItems: "center", justifyContent: "center", color: '#111' },
    timestamp: { textAlign: "center", fontSize: "0.8em", color: "#AAA", margin: "10px 0" },
    contextMenu: { position: "absolute", background: "#fff", border: "1px solid #eee", borderRadius: "8px", boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 1000, minWidth: "120px", overflow: "hidden" },
    contextItem: { padding: "10px 15px", cursor: "pointer", '&:hover': { backgroundColor: '#f5f5f5' } },
    errorBox: { backgroundColor: "#ffebee", color: "#d32f2f", padding: "10px", margin: "10px 20px", borderRadius: "8px", textAlign: "center" },
    loadingMoreIndicator: { textAlign: 'center', padding: '0.5rem', color: '#757575', fontSize: '0.9rem' },
    toggle: { position: "relative", display: "inline-block", width: "40px", height: "22px" },
    toggleInput: { opacity: 0, width: 0, height: 0 },
    slider: { position: "absolute", cursor: "pointer", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: safeMode ? "#FFD54F" : "#ccc", transition: ".4s", borderRadius: "22px" },
    sliderBefore: { position: "absolute", content: '""', height: "16px", width: "16px", left: safeMode ? "20px" : "3px", bottom: "3px", backgroundColor: "white", transition: ".4s", borderRadius: "50%" },
  };

  return (
    <div style={styles.container}>
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
            <NudgeLogo />
        </div>
        <div style={styles.sidebarSection}>
            <div style={styles.sidebarTitle}>Tools</div>
            <button style={styles.toolButton('chat')} onClick={() => setActiveTool('chat')} onMouseEnter={() => setHoveredTool('chat')} onMouseLeave={() => setHoveredTool('')}>💬 Chat</button>
            <button style={styles.toolButton('online_search')} onClick={() => setActiveTool('online_search')} onMouseEnter={() => setHoveredTool('online_search')} onMouseLeave={() => setHoveredTool('')}>🌐 Online Search</button>
            <button style={styles.toolButton('deep_research')} onClick={() => setActiveTool('deep_research')} onMouseEnter={() => setHoveredTool('deep_research')} onMouseLeave={() => setHoveredTool('')}>🔬 Deep Research</button>
        </div>
        <div style={{...styles.sidebarSection, marginTop: 'auto'}}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: 'space-between', padding: '10px 20px' }}>
                <span style={{fontSize: '14px', color: '#555'}}>Safe Mode</span>
                <label style={styles.toggle}>
                    <input type="checkbox" checked={safeMode} onChange={toggleSafeMode} style={styles.toggleInput} />
                    <span style={{...styles.slider, ...styles.sliderBefore}}></span>
                </label>
            </div>
        </div>
      </div>

      <div style={styles.main}>
        <div ref={messagesContainerRef} style={styles.chat}>
          {isFetchingMore && <div style={styles.loadingMoreIndicator}>Loading...</div>}
          {!isFetchingMore && messages.length === 0 && !hasMore && <p style={{ textAlign: 'center', padding: '1rem', color: '#888' }}>Hey! I'm Nudge. What's on your mind?</p>}
          {messages.map((msg, i) => (
            <MessageItem
              key={msg.id || `${msg.timestamp}-${i}`}
              msg={msg}
              index={i}
              prevMessageTimestamp={i > 0 ? messages[i - 1].timestamp : null}
              formatReplyPreview={formatReplyPreview}
              handleContextMenu={handleContextMenuCallback}
              editingIndex={editingIndex}
              editValue={editValue}
              setEditValue={setEditValue}
              saveEdit={saveEdit}
              styles={styles}
            />
          ))}
          <div ref={chatEndRef} />
        </div>

        {contextMenu.visible && (
          <div style={{ ...styles.contextMenu, top: contextMenu.y, left: contextMenu.x }}>
            <div onClick={handleEdit} style={{...styles.contextItem}}>✏️ Edit</div>
            <div onClick={handleDelete} style={{...styles.contextItem}}>🗑️ Delete</div>
            <div onClick={handleCopy} style={{...styles.contextItem}}>📋 Copy</div>
            <div onClick={handleReply} style={{...styles.contextItem}}>↩️ Reply</div>
          </div>
        )}

        {error && <div style={styles.errorBox}>{error}</div>}

        <div style={styles.inputWrapper}>
            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} style={styles.inputContainer}>
                <button type="button" style={styles.iconButton} onClick={() => alert('File upload coming soon!')}>
                    <PaperclipIcon />
                </button>
                <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    style={styles.textArea}
                    placeholder={getPlaceholderText()}
                />
                <button type="submit" disabled={loading || !input.trim()} style={styles.sendButton}>
                    {loading ? '...' : <SendIcon />}
                </button>
            </form>
        </div>
      </div>
    </div>
  );
}

export default Chat;

