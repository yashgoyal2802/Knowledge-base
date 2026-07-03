import React from 'react';
import { Shield, AlertTriangle, Sparkles, BookOpen, ArrowRight, Activity, Cpu, ShieldAlert } from 'lucide-react';
import ArticleCard from './ArticleCard';
import VulnCard from './VulnCard';

export default function Dashboard({ articles, vulns, stats, onNavigate }) {
  const topCriticalVulns = vulns.filter(v => v.severity === 'CRITICAL' || v.kev_due_date).slice(0, 3);
  const latestNews = articles.slice(0, 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
      {/* Hero Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(255, 107, 0, 0.15) 0%, rgba(18, 20, 24, 0.8) 100%)',
        border: '1px solid var(--border-hover)',
        borderRadius: 'var(--radius-lg)',
        padding: '2rem 2.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1.5rem',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{ maxWidth: '650px', zIndex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span className="badge badge-ai">
              <Sparkles size={12} /> GEMINI 2.0 FLASH RAG ENGINE
            </span>
            <span className="badge badge-stream" style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}>
              <Activity size={12} className="pulse-glow" /> LIVE FEED
            </span>
          </div>
          <h1 style={{ fontSize: '2.25rem', marginBottom: '0.5rem', lineHeight: '1.2' }}>
            Cybersecurity Intelligence & Threat Repository
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1rem', lineHeight: '1.6' }}>
            Autonomous real-time aggregation across NVD, CISA KEV, 9 news outlets, and 3 security research labs.
            Every item is automatically enriched with AI summaries, executive impact angles, and vector embeddings.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', zIndex: 1 }}>
          <button
            type="button"
            className="btn-primary"
            onClick={() => onNavigate('chat')}
            style={{ padding: '0.85rem 1.75rem', fontSize: '1rem' }}
          >
            <Sparkles size={18} />
            <span>Launch RAG Analyst Chat</span>
          </button>
          <button
            type="button"
            className="btn-outline"
            onClick={() => onNavigate('vulnerabilities')}
            style={{ padding: '0.75rem 1.75rem', justifyContent: 'center' }}
          >
            <span>View CISA KEV Feed</span>
            <ArrowRight size={16} />
          </button>
        </div>

        {/* Decorative Glow */}
        <div style={{
          position: 'absolute',
          right: '-5%',
          bottom: '-20%',
          width: '350px',
          height: '350px',
          background: 'radial-gradient(circle, var(--primary-glow) 0%, transparent 70%)',
          pointerEvents: 'none'
        }} />
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
            <BookOpen size={26} />
          </div>
          <div className="stat-info">
            <h4>Total Intelligence</h4>
            <div className="stat-value">{stats.totalArticles + stats.totalVulns || '---'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(239, 68, 68, 0.15)', color: 'var(--severity-critical)' }}>
            <ShieldAlert size={26} className="pulse-glow" />
          </div>
          <div className="stat-info">
            <h4>CISA KEV Active Alerts</h4>
            <div className="stat-value" style={{ color: 'var(--severity-critical)' }}>
              {stats.kevCount || '---'}
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(249, 115, 22, 0.15)', color: 'var(--severity-high)' }}>
            <AlertTriangle size={26} />
          </div>
          <div className="stat-info">
            <h4>Critical / High CVEs</h4>
            <div className="stat-value" style={{ color: 'var(--severity-high)' }}>
              {stats.criticalHighCount || '---'}
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#e879f9' }}>
            <Cpu size={26} />
          </div>
          <div className="stat-info">
            <h4>AI Enriched Rate</h4>
            <div className="stat-value" style={{ color: '#e879f9' }}>
              {stats.enrichedPercentage || '100%'}
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Section: Top Critical Vulns & Latest News */}
      <div className="two-col-layout">
        {/* Left: Critical Vulnerabilities */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <ShieldAlert size={22} color="var(--severity-critical)" />
              <h2 style={{ fontSize: '1.4rem' }}>High-Priority Threat Alerts (KEV / Critical)</h2>
            </div>
            <button
              type="button"
              onClick={() => onNavigate('vulnerabilities')}
              style={{ fontSize: '0.85rem', color: 'var(--primary)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <span>View All ({vulns.length})</span>
              <ArrowRight size={14} />
            </button>
          </div>

          <div className="feed-grid">
            {topCriticalVulns.length > 0 ? (
              topCriticalVulns.map(v => <VulnCard key={v.id} vuln={v} />)
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                No critical vulnerabilities or KEV items loaded yet.
              </div>
            )}
          </div>
        </div>

        {/* Right: Latest News & Research */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <BookOpen size={22} color="var(--primary)" />
              <h2 style={{ fontSize: '1.4rem' }}>Latest Intel Feed</h2>
            </div>
            <button
              type="button"
              onClick={() => onNavigate('timeline')}
              style={{ fontSize: '0.85rem', color: 'var(--primary)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <span>View All ({articles.length})</span>
              <ArrowRight size={14} />
            </button>
          </div>

          <div className="feed-grid">
            {latestNews.length > 0 ? (
              latestNews.map(a => <ArticleCard key={a.id} article={a} />)
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                No news articles loaded yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
