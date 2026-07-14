import React, { useState } from 'react';
import { Sparkles, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

/** Relative time string for display */
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

const SEVERITY_COLORS = {
  CRITICAL: 'var(--severity-critical)',
  HIGH: 'var(--severity-high)',
  MEDIUM: 'var(--severity-medium)',
  LOW: 'var(--severity-low)',
};

export default function VulnCard({ vuln }) {
  const [showAI, setShowAI] = useState(false);
  const hasAI = vuln.enriched && (vuln.summary_bullets?.length > 0 || vuln.business_angle);
  const color = SEVERITY_COLORS[vuln.severity] || 'var(--text-tertiary)';
  const severityBg = `var(--severity-${(vuln.severity || '').toLowerCase()}-bg)`;

  return (
    <div className="vuln-item">
      {/* Header: severity dot + CVE ID + severity label + KEV badge */}
      <div className="vuln-header">
        <span className="severity-dot" style={{ background: color }} />
        <span className="vuln-cve">{vuln.cve_id}</span>
        <span className="severity-label" style={{ background: severityBg, color }}>
          {vuln.severity}
        </span>
        {vuln.kev_due_date && <span className="kev-badge">CISA KEV</span>}
      </div>

      {/* Plain-English description */}
      {vuln.description && (
        <p className="vuln-description">{vuln.description}</p>
      )}

      {/* Metadata row */}
      <div className="vuln-meta">
        <span>{timeAgo(vuln.published_at)}</span>
        {vuln.kev_due_date && <span>Due: {vuln.kev_due_date}</span>}
        {vuln.kev_known_ransomware && (
          <span style={{ color: 'var(--severity-critical)', fontWeight: 600 }}>⚠ Ransomware linked</span>
        )}
        <a
          href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
        >
          NVD <ExternalLink size={12} />
        </a>
      </div>

      {/* AI toggle */}
      <div className="article-footer" style={{ marginTop: '0.5rem' }}>
        <span />
        {hasAI && (
          <button className="ai-toggle" onClick={() => setShowAI(!showAI)}>
            <Sparkles size={14} />
            <span>AI Analysis</span>
            {showAI ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Collapsible AI panel */}
      {showAI && hasAI && (
        <div className="ai-panel">
          {vuln.summary_bullets?.length > 0 && (
            <ul className="ai-bullets">
              {vuln.summary_bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          )}

          {vuln.business_angle && (
            <div className="ai-insight">
              <div className="ai-insight-label">Impact</div>
              {vuln.business_angle}
            </div>
          )}

          {vuln.interview_nugget && (
            <div className="ai-insight">
              <div className="ai-insight-label">Interview talking point</div>
              &ldquo;{vuln.interview_nugget}&rdquo;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
