import React, { useState, useEffect, useCallback } from 'react';
import { Search } from 'lucide-react';
import ArticleCard from './ArticleCard';
import VulnCard from './VulnCard';

/**
 * Unified feed component. Renders either articles or vulnerabilities
 * based on the `mode` prop.
 *
 * - mode="articles" → News feed with stream filter (All / News / Research)
 * - mode="vulns"    → Vulnerability list with severity filter
 */
export default function InfiniteTimeline({ mode }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Article-specific filter
  const [streamFilter, setStreamFilter] = useState('');

  // Vulnerability-specific filters
  const [severityFilter, setSeverityFilter] = useState('');
  const [kevOnly, setKevOnly] = useState(false);

  const fetchItems = useCallback(async (pageNum = 1, append = false) => {
    setLoading(true);
    try {
      let url;
      if (mode === 'articles') {
        if (searchQuery.trim()) {
          url = `/api/articles/search?q=${encodeURIComponent(searchQuery.trim())}&limit=20`;
        } else {
          url = `/api/articles?page=${pageNum}&page_size=20`;
          if (streamFilter) url += `&stream=${streamFilter}`;
        }
      } else {
        url = `/api/vulnerabilities?page=${pageNum}&page_size=20`;
        if (severityFilter) url += `&severity=${severityFilter}`;
        if (kevOnly) url += `&kev_only=true`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error(`API ${res.status}`);

      const data = await res.json();
      const newItems = data.items || [];
      setItems((prev) => (append ? [...prev, ...newItems] : newItems));
      setHasMore(data.has_more ?? newItems.length >= 20);
    } catch {
      // Offline fallback — show demo data on first load only
      if (!append) {
        setItems(mode === 'articles' ? getDemoArticles() : getDemoVulns());
      }
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [mode, streamFilter, severityFilter, kevOnly, searchQuery]);

  // Reset and fetch when mode or filters change
  useEffect(() => {
    setPage(1);
    fetchItems(1, false);
  }, [fetchItems]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    fetchItems(1, false);
  };

  const handleLoadMore = () => {
    const next = page + 1;
    setPage(next);
    fetchItems(next, true);
  };

  return (
    <div>
      {/* Search bar */}
      <form onSubmit={handleSearch} className="search-wrapper">
        <Search size={16} className="search-icon" />
        <input
          type="text"
          className="search-field"
          placeholder={mode === 'articles' ? 'Search articles…' : 'Search vulnerabilities…'}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </form>

      {/* Filter tabs */}
      <div className="feed-filters">
        {mode === 'articles' ? (
          <>
            <button
              className={`filter-tab ${!streamFilter ? 'active' : ''}`}
              onClick={() => setStreamFilter('')}
            >
              All
            </button>
            <button
              className={`filter-tab ${streamFilter === 'news' ? 'active' : ''}`}
              onClick={() => setStreamFilter('news')}
            >
              News
            </button>
            <button
              className={`filter-tab ${streamFilter === 'research' ? 'active' : ''}`}
              onClick={() => setStreamFilter('research')}
            >
              Research
            </button>
          </>
        ) : (
          <>
            <button
              className={`filter-tab ${!severityFilter && !kevOnly ? 'active' : ''}`}
              onClick={() => { setSeverityFilter(''); setKevOnly(false); }}
            >
              All
            </button>
            <button
              className={`filter-tab ${severityFilter === 'CRITICAL' ? 'active' : ''}`}
              onClick={() => { setSeverityFilter('CRITICAL'); setKevOnly(false); }}
            >
              Critical
            </button>
            <button
              className={`filter-tab ${severityFilter === 'HIGH' ? 'active' : ''}`}
              onClick={() => { setSeverityFilter('HIGH'); setKevOnly(false); }}
            >
              High
            </button>
            <button
              className={`filter-tab ${kevOnly ? 'active' : ''}`}
              onClick={() => { setKevOnly(!kevOnly); setSeverityFilter(''); }}
            >
              CISA KEV
            </button>
          </>
        )}
      </div>

      {/* Feed list */}
      <div className="feed-list">
        {items.map((item, idx) =>
          mode === 'articles'
            ? <ArticleCard key={item.id || idx} article={item} />
            : <VulnCard key={item.id || idx} vuln={item} />
        )}
      </div>

      {/* States: loading, empty, load more */}
      {loading && items.length === 0 && (
        <div className="loading-text">Loading…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="empty-state">
          <h3>No items found</h3>
          <p>
            {mode === 'articles'
              ? 'No articles match your filters. Try a different search or filter.'
              : 'No vulnerabilities match your filters.'}
          </p>
        </div>
      )}

      {!loading && hasMore && items.length > 0 && (
        <button className="load-more-btn" onClick={handleLoadMore}>
          Load more
        </button>
      )}

      {loading && items.length > 0 && (
        <div className="loading-text">Loading more…</div>
      )}
    </div>
  );
}


// ── Demo data for offline preview ────────────────────────────────

function getDemoArticles() {
  return [
    {
      id: 'demo-1',
      title: 'Google Mandiant Unveils AI Cyber Defense Agent for Real-Time SOC Remediation',
      url: 'https://cloud.google.com/blog/topics/threat-intelligence',
      source: 'mandiant_threat_intel',
      stream: 'news',
      author: 'Kevin Mandia',
      published_at: new Date(Date.now() - 3600000).toISOString(),
      raw_content: 'Mandiant researchers demonstrate a new multi-agent cybersecurity framework capable of triaging SOC alerts with 99.4% accuracy. The system leverages Gemini 2.0 Flash reasoning to correlate cross-cloud IAM telemetry, firewall logs, and endpoint memory dumps in real time.',
      tags: ['AI Security', 'SOC Automation', 'Gemini 2.0'],
      enriched: true,
      summary_bullets: [
        'Multi-agent framework triages SOC alerts with 99.4% accuracy using Gemini 2.0 Flash.',
        'Correlates cross-cloud IAM telemetry, firewall logs, and endpoint memory dumps in real time.',
        'Early deployments report 85% reduction in Mean Time To Remediate for ransomware activity.',
      ],
      business_angle: 'Automating Tier-1 and Tier-2 SOC triage alleviates cybersecurity talent shortages while responding to machine-speed attacks.',
      interview_nugget: 'Modern SOC automation requires moving beyond static SOAR playbooks to agentic workflows that dynamically formulate hypotheses.',
    },
    {
      id: 'demo-2',
      title: 'NIST Releases Post-Quantum Cryptography Implementation Guidance',
      url: 'https://www.bleepingcomputer.com',
      source: 'bleeping_computer',
      stream: 'news',
      author: 'Lawrence Abrams',
      published_at: new Date(Date.now() - 7200000).toISOString(),
      raw_content: 'NIST has officially mandated migration timelines for FIPS 203, 204, and 205 quantum-resistant standards, warning against Store Now Decrypt Later espionage tactics targeting financial and defense sectors.',
      tags: ['Post-Quantum', 'Cryptography', 'NIST'],
      enriched: true,
      summary_bullets: [
        'NIST mandates migration timelines for ML-KEM, ML-DSA, and SLH-DSA quantum-resistant standards.',
        'Warns against Store Now, Decrypt Later espionage targeting financial and defense sectors.',
        'Organizations must transition TLS handshakes to hybrid Kyber algorithms by Q4 2026.',
      ],
      business_angle: 'Quantum computing threats are an immediate risk to long-life sensitive data.',
      interview_nugget: 'Hybrid cryptographic protocols combining ECDH with lattice-based ML-KEM provide defense-in-depth during the quantum transition.',
    },
    {
      id: 'demo-3',
      title: 'Zero-Trust Architecture Stops Massive OAuth Phishing Campaign',
      url: 'https://www.wired.com',
      source: 'wired_security',
      stream: 'news',
      published_at: new Date(Date.now() - 14400000).toISOString(),
      raw_content: 'A global campaign targeting Fortune 500 cloud tenants attempted to bypass legacy MFA via illicit OAuth consent grants. Organizations enforcing FIDO2 hardware tokens blocked all compromise attempts.',
      tags: ['Zero-Trust', 'OAuth', 'Identity Security'],
      enriched: true,
      summary_bullets: [
        'Fortune 500 cloud tenants targeted via illicit OAuth application consent grants.',
        'FIDO2/WebAuthn hardware tokens blocked all compromise attempts.',
        'Threat actors shifting from credential stuffing to token hijacking and session exfiltration.',
      ],
      business_angle: 'Traditional MFA is obsolete against adversary-in-the-middle phishing kits. FIDO2 is essential.',
      interview_nugget: 'Identity is the primary security perimeter in cloud architectures; monitoring OAuth token scopes stops lateral movement.',
    },
    {
      id: 'demo-4',
      title: 'DeepSeek-R1 AI Architecture Analyzed for Automated Exploit Generation',
      url: 'https://darkreading.com',
      source: 'dark_reading',
      stream: 'research',
      author: 'Kelly Jackson Higgins',
      published_at: new Date(Date.now() - 28800000).toISOString(),
      raw_content: 'Security researchers demonstrate that open-weight reasoning models like DeepSeek-R1 can autonomously discover complex race conditions in Linux kernel drivers with a 42% success rate in generating working PoC exploits.',
      tags: ['LLM', 'Vulnerability Research', 'AI Defense'],
      enriched: true,
      summary_bullets: [
        'Open-weight reasoning models can discover complex race conditions in Linux kernel drivers.',
        'The model achieved 42% success rate generating working proof-of-concept exploits from decompiled binaries.',
        'Defensive teams adapting reasoning traces for root-cause analysis and verified patch generation.',
      ],
      business_angle: 'AI reasoning models compress the timeline between vulnerability disclosure and exploitation from weeks to hours.',
      interview_nugget: 'Offensive AI only needs to find one flaw; defensive AI must formally prove safety across all paths.',
    },
  ];
}

function getDemoVulns() {
  return [
    {
      id: 'demo-v1',
      cve_id: 'CVE-2024-3400',
      source: 'kev',
      severity: 'CRITICAL',
      description: 'A command injection vulnerability in PAN-OS GlobalProtect allows unauthenticated remote code execution with root privileges on affected firewalls.',
      kev_due_date: '2024-04-19',
      kev_known_ransomware: true,
      published_at: new Date(Date.now() - 86400000).toISOString(),
      enriched: true,
      summary_bullets: [
        'Unauthenticated RCE with root privileges on PAN-OS GlobalProtect gateways.',
        'Active exploitation by state-sponsored actors and ransomware syndicates.',
        'Telemetry feature must be enabled; patching is mandatory.',
      ],
      business_angle: 'CVSS 10.0 perimeter vulnerability actively exploited. Emergency patching required.',
      interview_nugget: 'Edge devices running as root must employ strict sandboxing and privilege separation.',
    },
    {
      id: 'demo-v2',
      cve_id: 'CVE-2024-23897',
      source: 'nvd',
      severity: 'CRITICAL',
      description: 'Jenkins CLI argument expansion vulnerability allows unauthenticated attackers to read arbitrary files on the controller file system, including SSH keys and API secrets.',
      published_at: new Date(Date.now() - 172800000).toISOString(),
      enriched: true,
      summary_bullets: [
        'Arbitrary file read via Jenkins CLI @ character expansion.',
        'Attackers can access cryptographic keys, SSH credentials, and environment variables.',
        'Escalatable to RCE if Resource Root URL or specific plugins are enabled.',
      ],
      business_angle: 'CI/CD servers hold keys to the entire software supply chain.',
      interview_nugget: 'Arbitrary file reads on CI/CD orchestrators are equivalent to RCE because build masters store secrets in plaintext.',
    },
  ];
}
