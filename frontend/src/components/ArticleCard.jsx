import React, { useState } from 'react';
import { ExternalLink, Sparkles, Briefcase, MessageSquare, Clock, Tag, User } from 'lucide-react';

export default function ArticleCard({ article }) {
  const [showEnrichment, setShowEnrichment] = useState(true);

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown pub date';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short',
    });
  };

  const formatSource = (src) => {
    return src.replace(/_/g, ' ').toUpperCase();
  };

  return (
    <article className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {/* Card Header: Badges & Time */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="badge badge-source">{formatSource(article.source)}</span>
          <span className="badge badge-stream">{article.stream.toUpperCase()}</span>
          {article.enriched && (
            <span className="badge badge-ai">
              <Sparkles size={12} /> AI ENRICHED
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
          <Clock size={14} />
          <time dateTime={article.published_at}>{formatDate(article.published_at)}</time>
        </div>
      </div>

      {/* Title & Link */}
      <h3 style={{ fontSize: '1.2rem', lineHeight: '1.35', margin: '0.25rem 0' }}>
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}
        >
          <span>{article.title}</span>
          <ExternalLink size={18} style={{ flexShrink: 0, marginTop: '3px', color: 'var(--primary)' }} />
        </a>
      </h3>

      {/* Author & Tags */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        {article.author && (
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <User size={13} /> {article.author}
          </span>
        )}
        {article.tags && article.tags.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
            <Tag size={13} />
            {article.tags.slice(0, 4).map((tag, idx) => (
              <span key={idx} style={{ background: 'var(--bg-search)', padding: '0.15rem 0.5rem', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* AI Enrichment Box */}
      {article.enriched && (article.summary_bullets?.length > 0 || article.business_angle) && (
        <div className="ai-box">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div className="ai-box-title">
              <Sparkles size={15} /> GEMINI 2.0 FLASH INTELLIGENCE
            </div>
            <button
              type="button"
              onClick={() => setShowEnrichment(!showEnrichment)}
              style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textDecoration: 'underline' }}
            >
              {showEnrichment ? 'Collapse' : 'Expand'}
            </button>
          </div>

          {showEnrichment && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {article.summary_bullets && article.summary_bullets.length > 0 && (
                <ul className="ai-bullets">
                  {article.summary_bullets.map((bullet, idx) => (
                    <li key={idx}>{bullet}</li>
                  ))}
                </ul>
              )}

              {article.business_angle && (
                <div style={{ background: 'var(--primary-glow)', padding: '0.65rem 0.85rem', borderRadius: '6px', borderLeft: '2px solid var(--primary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary)', marginBottom: '0.25rem' }}>
                    <Briefcase size={14} /> CISO / BUSINESS IMPACT
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', margin: 0 }}>{article.business_angle}</p>
                </div>
              )}

              {article.interview_nugget && (
                <div className="ai-nugget">
                  <MessageSquare size={16} style={{ flexShrink: 0, color: '#e879f9', marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: '#f0abfc', marginRight: '0.35rem' }}>Interview Talking Point:</strong>
                    <span>"{article.interview_nugget}"</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
