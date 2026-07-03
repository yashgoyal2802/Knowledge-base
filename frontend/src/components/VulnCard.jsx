import React, { useState } from 'react';
import { ShieldAlert, ExternalLink, Sparkles, Briefcase, MessageSquare, AlertTriangle, Clock, Server, CheckCircle2 } from 'lucide-react';

export default function VulnCard({ vuln }) {
  const [showEnrichment, setShowEnrichment] = useState(true);

  const formatSeverity = (sev) => {
    if (!sev) return 'UNKNOWN';
    return sev.toUpperCase();
  };

  const getCvssColor = (score) => {
    if (!score) return 'var(--text-dim)';
    if (score >= 9.0) return 'var(--severity-critical)';
    if (score >= 7.0) return 'var(--severity-high)';
    if (score >= 4.0) return 'var(--severity-medium)';
    return 'var(--severity-low)';
  };

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

  return (
    <article className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
      {/* Top Header: CVE ID, Severity, CVSS Score */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span className="badge badge-cve">{vuln.cve_id}</span>
          <span className={`badge severity-${formatSeverity(vuln.severity)}`}>
            {formatSeverity(vuln.severity)}
          </span>
          <span className="badge badge-source">{vuln.source.toUpperCase()}</span>
          {vuln.enriched && (
            <span className="badge badge-ai">
              <Sparkles size={12} /> AI ENRICHED
            </span>
          )}
        </div>

        {vuln.cvss_v3_score && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'rgba(0,0,0,0.4)', padding: '0.25rem 0.75rem', borderRadius: 'var(--radius-full)', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 'bold' }}>CVSS v3:</span>
            <strong style={{ color: getCvssColor(vuln.cvss_v3_score), fontSize: '1rem', fontFamily: 'var(--font-mono)' }}>
              {vuln.cvss_v3_score.toFixed(1)}
            </strong>
          </div>
        )}
      </div>

      {/* CISA KEV Alert Banner */}
      {vuln.kev_due_date && (
        <div style={{
          background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.05))',
          border: '1px solid var(--severity-critical)',
          borderRadius: 'var(--radius-md)',
          padding: '0.75rem 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.5rem',
          boxShadow: '0 0 15px rgba(239, 68, 68, 0.15)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#fca5a5', fontWeight: 'bold', fontSize: '0.85rem' }}>
            <AlertTriangle className="pulse-glow" size={18} color="var(--severity-critical)" />
            <span>CISA KNOWN EXPLOITED VULNERABILITY (KEV)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8rem', color: '#fee2e2' }}>
            {vuln.kev_known_ransomware && (
              <span style={{ background: 'var(--severity-critical)', color: '#fff', padding: '0.15rem 0.5rem', borderRadius: '4px', fontWeight: 'bold', fontSize: '0.7rem' }}>
                RANSOMWARE LINKED
              </span>
            )}
            <span>Remediation Due: <strong style={{ textDecoration: 'underline' }}>{vuln.kev_due_date}</strong></span>
          </div>
        </div>
      )}

      {/* Description */}
      <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: '1.5', margin: '0.25rem 0' }}>
        {vuln.description || 'No description provided by NVD/CISA.'}
      </p>

      {/* Metadata & CPE Preview */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.6rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Clock size={14} /> Published: <time dateTime={vuln.published_at}>{formatDate(vuln.published_at)}</time>
        </div>

        <a
          href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--primary)', fontWeight: '600' }}
        >
          <span>View NVD Advisory</span>
          <ExternalLink size={14} />
        </a>
      </div>

      {/* AI Enrichment Box */}
      {vuln.enriched && (vuln.summary_bullets?.length > 0 || vuln.business_angle) && (
        <div className="ai-box">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div className="ai-box-title">
              <Sparkles size={15} /> GEMINI 2.0 FLASH THREAT ANALYSIS
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
              {vuln.summary_bullets && vuln.summary_bullets.length > 0 && (
                <ul className="ai-bullets">
                  {vuln.summary_bullets.map((bullet, idx) => (
                    <li key={idx}>{bullet}</li>
                  ))}
                </ul>
              )}

              {vuln.business_angle && (
                <div style={{ background: 'var(--primary-glow)', padding: '0.65rem 0.85rem', borderRadius: '6px', borderLeft: '2px solid var(--primary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--primary)', marginBottom: '0.25rem' }}>
                    <Briefcase size={14} /> CISO RISK ASSESSMENT & REMEDIATION
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', margin: 0 }}>{vuln.business_angle}</p>
                </div>
              )}

              {vuln.interview_nugget && (
                <div className="ai-nugget">
                  <MessageSquare size={16} style={{ flexShrink: 0, color: '#e879f9', marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: '#f0abfc', marginRight: '0.35rem' }}>Interview Talking Point:</strong>
                    <span>"{vuln.interview_nugget}"</span>
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
