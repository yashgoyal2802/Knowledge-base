import React, { useState, useRef, useEffect } from 'react';
import { Send, RefreshCw } from 'lucide-react';

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      content: 'Hi! I can help you understand cybersecurity trends, explain CVEs, or discuss topics for interview prep. What would you like to know?',
      sources: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  const suggestions = [
    'What are the latest ransomware trends?',
    'Explain zero-trust architecture',
    'What is the CISA KEV catalog?',
    'How does post-quantum cryptography work?',
  ];

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (text) => {
    const query = (text || input).trim();
    if (!query || isStreaming) return;

    const userMsg = { role: 'user', content: query };
    const aiMsg = { role: 'ai', content: '', sources: [], isStreaming: true };
    setMessages((prev) => [...prev, userMsg, aiMsg]);
    if (!text) setInput('');
    setIsStreaming(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, stream: true }),
      });

      if (!res.ok) throw new Error(`${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';
      let sources = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'token') {
              accumulated += data.content;
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { role: 'ai', content: accumulated, sources, isStreaming: true };
                return next;
              });
            } else if (data.type === 'sources' || data.type === 'source') {
              sources = Array.isArray(data.sources) ? data.sources : [data];
            } else if (data.type === 'done' || data.type === 'error') {
              break;
            }
          } catch {
            // Skip malformed SSE frames
          }
        }
      }

      // Finalize message
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: 'ai', content: accumulated || 'No response received.', sources };
        return next;
      });
    } catch {
      // Offline fallback — simulate a streaming response
      const fallback = `That's a great question about "${query}". In the cybersecurity landscape, this topic is actively evolving. I'd recommend checking recent advisories from CISA, NIST frameworks, and industry reports from sources like Mandiant and CrowdStrike for the latest guidance.`;
      let i = 0;
      const words = fallback.split(' ');
      const interval = setInterval(() => {
        i++;
        const partial = words.slice(0, i).join(' ');
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { role: 'ai', content: partial, sources: [], isStreaming: i < words.length };
          return next;
        });
        if (i >= words.length) clearInterval(interval);
      }, 40);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-wrap">
      {/* Messages */}
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-bubble ${msg.role}`}>
            <div style={{ whiteSpace: 'pre-line' }}>
              {msg.content || (msg.isStreaming ? '…' : '')}
              {msg.isStreaming && (
                <span
                  className="animate-pulse"
                  style={{
                    display: 'inline-block',
                    width: '6px',
                    height: '14px',
                    background: msg.role === 'user' ? 'var(--text-inverse)' : 'var(--accent)',
                    marginLeft: '3px',
                    verticalAlign: 'middle',
                    borderRadius: '1px',
                  }}
                />
              )}
            </div>

            {/* Citation chips */}
            {msg.sources?.length > 0 && (
              <div className="chat-sources">
                {msg.sources.map((src, i) => (
                  <a
                    key={i}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="chat-source-chip"
                  >
                    {src.title?.slice(0, 40) || `Source ${i + 1}`}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions — only shown at the start */}
      {messages.length <= 2 && !isStreaming && (
        <div className="chat-suggestions">
          {suggestions.map((q, i) => (
            <button key={i} className="suggestion-chip" onClick={() => handleSend(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="chat-input-bar">
        <textarea
          className="chat-input"
          rows={1}
          placeholder="Ask about cybersecurity topics…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          className="send-btn"
          disabled={isStreaming || !input.trim()}
          onClick={() => handleSend()}
          aria-label="Send message"
        >
          {isStreaming ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </div>
    </div>
  );
}
