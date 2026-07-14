import React, { useState } from 'react';
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * Returns a relative time string ("3h ago", "2d ago") for display,
 * with the exact UTC date available via the title attribute.
 */
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '';
  const diff = Math.floor((now - date) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Full UTC timestamp for hover tooltip */
function formatExact(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short',
  });
}

/** Convert source_key to readable name */
function formatSource(src) {
  if (!src) return '';
  return src.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ArticleCard({ article }) {
  const [showAI, setShowAI] = useState(false);
  const hasAI = article.enriched && (article.summary_bullets?.length > 0 || article.business_angle);

  return (
    <div className="article-item">
      {/* Meta: source · time · author */}
      <div className="article-meta">
        <span className="article-source">{formatSource(article.source)}</span>
        <span>·</span>
        <time dateTime={article.published_at} title={formatExact(article.published_at)}>
          {timeAgo(article.published_at)}
        </time>
        {article.author && (
          <>
            <span>·</span>
            <span>{article.author}</span>
          </>
        )}
      </div>

      {/* Title — large, bold, clickable */}
      <h3 className="article-title">
        <a href={article.url} target="_blank" rel="noopener noreferrer">
          {article.title}
        </a>
      </h3>

      {/* Content excerpt — first few lines of raw_content */}
      {article.raw_content && (
        <p className="article-excerpt">{article.raw_content}</p>
      )}

      {/* Footer: tags + AI toggle */}
      <div className="article-footer">
        {article.tags?.length > 0 ? (
          <span className="article-tags">
            {article.tags.slice(0, 5).join(' · ')}
          </span>
        ) : (
          <span />
        )}

        {hasAI && (
          <button className="ai-toggle" onClick={() => setShowAI(!showAI)}>
            <Sparkles size={14} />
            <span>AI Summary</span>
            {showAI ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Collapsible AI enrichment panel */}
      {showAI && hasAI && (
        <div className="ai-panel">
          {article.summary_bullets?.length > 0 && (
            <ul className="ai-bullets">
              {article.summary_bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          )}

          {article.business_angle && (
            <div className="ai-insight">
              <div className="ai-insight-label">Why it matters</div>
              {article.business_angle}
            </div>
          )}

          {article.interview_nugget && (
            <div className="ai-insight">
              <div className="ai-insight-label">Interview talking point</div>
              &ldquo;{article.interview_nugget}&rdquo;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
