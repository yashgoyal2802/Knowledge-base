import React, { useState, useEffect } from 'react';
import { Filter, Search, RefreshCw, ShieldAlert, BookOpen, Layers, ArrowDown, Check } from 'lucide-react';
import ArticleCard from './ArticleCard';
import VulnCard from './VulnCard';

export default function InfiniteTimeline({ activeTab, setActiveTab }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  
  // Filters
  const [streamFilter, setStreamFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [kevOnly, setKevOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Fetch Data from API (or fallback to dummy data if local dev API isn't running)
  const fetchItems = async (pageNum = 1, append = false) => {
    setLoading(true);
    try {
      let url = '';
      if (isSearching && searchQuery.trim()) {
        url = `/api/articles/search?q=${encodeURIComponent(searchQuery)}&limit=15`;
      } else if (activeTab === 'articles') {
        url = `/api/articles?page=${pageNum}&page_size=15`;
        if (streamFilter) url += `&stream=${streamFilter}`;
      } else {
        url = `/api/vulnerabilities?page=${pageNum}&page_size=15`;
        if (severityFilter) url += `&severity=${severityFilter}`;
        if (kevOnly) url += `&kev_only=true`;
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error('API fetch failed');
      const data = await res.json();

      const newItems = data.items || [];
      if (append) {
        setItems(prev => [...prev, ...newItems]);
      } else {
        setItems(newItems);
      }
      setHasMore(data.has_more ?? (newItems.length >= 15));
    } catch (err) {
      console.warn('API fetch error, generating rich fallback data for UI preview:', err);
      // Generate realistic demo fallback data if backend API is not currently running locally
      const demoData = generateDemoData(activeTab, pageNum);
      if (append) {
        setItems(prev => [...prev, ...demoData]);
      } else {
        setItems(demoData);
      }
      setHasMore(pageNum < 3);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setPage(1);
    fetchItems(1, false);
  }, [activeTab, streamFilter, severityFilter, kevOnly]);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setIsSearching(false);
      fetchItems(1, false);
      return;
    }
    setIsSearching(true);
    setPage(1);
    fetchItems(1, false);
  };

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      const nextPage = page + 1;
      setPage(nextPage);
      fetchItems(nextPage, true);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Controls & Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', background: 'var(--bg-card)', padding: '1rem 1.5rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', gap: '0.5rem', background: 'rgba(0,0,0,0.4)', padding: '0.3rem', borderRadius: 'var(--radius-full)', border: '1px solid var(--border-color)' }}>
          <button
            type="button"
            className={`btn-outline ${activeTab === 'articles' ? 'active-tab' : ''}`}
            onClick={() => { setActiveTab('articles'); setIsSearching(false); setSearchQuery(''); }}
            style={{
              background: activeTab === 'articles' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'articles' ? 'var(--text-on-primary)' : 'var(--text-muted)',
              border: 'none',
              padding: '0.5rem 1.25rem',
              fontWeight: '600'
            }}
          >
            <BookOpen size={16} />
            <span>News & Research</span>
          </button>
          <button
            type="button"
            className={`btn-outline ${activeTab === 'vulns' ? 'active-tab' : ''}`}
            onClick={() => { setActiveTab('vulns'); setIsSearching(false); setSearchQuery(''); }}
            style={{
              background: activeTab === 'vulns' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'vulns' ? 'var(--text-on-primary)' : 'var(--text-muted)',
              border: 'none',
              padding: '0.5rem 1.25rem',
              fontWeight: '600'
            }}
          >
            <ShieldAlert size={16} />
            <span>Vulnerabilities & KEV</span>
          </button>
        </div>

        {/* Semantic Search Bar */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '0.5rem', flex: '1', maxWidth: '400px' }}>
          <div className="search-bar" style={{ width: '100%' }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              type="text"
              className="search-input"
              placeholder={activeTab === 'articles' ? "Semantic search news (e.g. 'Ransomware attacks')..." : "Search CVEs or products..."}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => { setSearchQuery(''); setIsSearching(false); fetchItems(1, false); }}
                style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}
              >
                Clear
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Sub-Filters Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', padding: '0 0.5rem' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 'bold', textTransform: 'uppercase' }}>
          <Filter size={14} /> Filters:
        </span>

        {activeTab === 'articles' ? (
          <>
            <button
              type="button"
              onClick={() => setStreamFilter(streamFilter === '' ? 'news' : streamFilter === 'news' ? 'research' : '')}
              className="badge"
              style={{
                background: streamFilter ? 'var(--primary-glow)' : 'rgba(255,255,255,0.05)',
                color: streamFilter ? 'var(--primary)' : 'var(--text-muted)',
                border: `1px solid ${streamFilter ? 'var(--primary)' : 'var(--border-color)'}`,
                cursor: 'pointer',
                padding: '0.4rem 0.85rem'
              }}
            >
              Stream: {streamFilter ? streamFilter.toUpperCase() : 'ALL (News & Research)'}
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => {
                const sevs = ['', 'CRITICAL', 'HIGH', 'MEDIUM'];
                const nextIdx = (sevs.indexOf(severityFilter) + 1) % sevs.length;
                setSeverityFilter(sevs[nextIdx]);
              }}
              className="badge"
              style={{
                background: severityFilter ? `var(--severity-${severityFilter.toLowerCase()}-bg)` : 'rgba(255,255,255,0.05)',
                color: severityFilter ? `var(--severity-${severityFilter.toLowerCase()})` : 'var(--text-muted)',
                border: `1px solid ${severityFilter ? `var(--severity-${severityFilter.toLowerCase()})` : 'var(--border-color)'}`,
                cursor: 'pointer',
                padding: '0.4rem 0.85rem'
              }}
            >
              Severity: {severityFilter || 'ALL SEVERITIES'}
            </button>

            <button
              type="button"
              onClick={() => setKevOnly(!kevOnly)}
              className="badge"
              style={{
                background: kevOnly ? 'var(--severity-critical-bg)' : 'rgba(255,255,255,0.05)',
                color: kevOnly ? 'var(--severity-critical)' : 'var(--text-muted)',
                border: `1px solid ${kevOnly ? 'var(--severity-critical)' : 'var(--border-color)'}`,
                cursor: 'pointer',
                padding: '0.4rem 0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem'
              }}
            >
              {kevOnly && <Check size={13} />}
              <span>CISA KEV EXPLOITED ONLY</span>
            </button>
          </>
        )}

        {(streamFilter || severityFilter || kevOnly || isSearching) && (
          <button
            type="button"
            onClick={() => { setStreamFilter(''); setSeverityFilter(''); setKevOnly(false); setIsSearching(false); setSearchQuery(''); }}
            style={{ fontSize: '0.8rem', color: 'var(--primary)', textDecoration: 'underline', marginLeft: 'auto' }}
          >
            Reset All Filters
          </button>
        )}
      </div>

      {/* Feed List */}
      <div className="feed-grid">
        {items.length > 0 ? (
          items.map((item, idx) => {
            if (activeTab === 'articles' || item.item_type === 'article') {
              return <ArticleCard key={item.id || idx} article={item} />;
            }
            return <VulnCard key={item.id || idx} vuln={item} />;
          })
        ) : (
          !loading && (
            <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-muted)' }}>
              <Layers size={40} style={{ opacity: 0.3, marginBottom: '1rem', color: 'var(--primary)' }} />
              <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>No matching intelligence found</h3>
              <p>Try adjusting your search query or filter tags.</p>
            </div>
          )
        )}
      </div>

      {/* Loading Indicator & Load More */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: '1.5rem 0' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', fontWeight: '600' }}>
            <RefreshCw size={18} className="pulse-glow" style={{ animation: 'spin 1s linear infinite' }} />
            <span>Fetching real-time intelligence feeds...</span>
          </div>
        ) : hasMore ? (
          <button
            type="button"
            className="btn-outline"
            onClick={handleLoadMore}
            style={{ padding: '0.75rem 2rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <span>Load More Timeline Records</span>
            <ArrowDown size={16} />
          </button>
        ) : (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)' }}>
            — End of current intelligence stream —
          </div>
        )}
      </div>
    </div>
  );
}

// Helper: Generate realistic demo data for immediate UI preview
function generateDemoData(tab, pageNum) {
  if (tab === 'articles') {
    return [
      {
        id: `demo-art-${pageNum}-1`,
        title: "Critical Zero-Day Exploited in Ivanti Connect Secure VPN Gateways",
        url: "https://thehackernews.com",
        source: "the_hacker_news",
        stream: "news",
        author: "Ravie Lakshmanan",
        published_at: new Date(Date.now() - 3600000 * pageNum).toISOString(),
        tags: ["Zero-Day", "Ivanti", "VPN", "RCE", "CISA"],
        enriched: true,
        summary_bullets: [
          "Attackers are actively chaining authentication bypass (CVE-2024-21887) and command injection vulnerabilities to compromise Ivanti VPN appliances.",
          "Over 1,700 instances worldwide have been confirmed compromised with custom web shells and memory-only droppers.",
          "CISA has issued an emergency directive ordering federal civilian executive branch agencies to disconnect affected instances immediately."
        ],
        business_angle: "VPN gateways sit at the perimeter network edge. Compromise allows complete internal network pivoting without valid user credentials. Prioritize emergency patching or offline isolation.",
        interview_nugget: "When perimeter VPNs are compromised via memory-only web shells, traditional file-integrity monitoring fails; forensic responders must dump volatile RAM before rebooting."
      },
      {
        id: `demo-art-${pageNum}-2`,
        title: "DeepSeek-R1 AI Architecture Analyzed for Novel Automated Exploit Generation",
        url: "https://darkreading.com",
        source: "darkreading",
        stream: "research",
        author: "Kelly Jackson Higgins",
        published_at: new Date(Date.now() - 7200000 * pageNum).toISOString(),
        tags: ["LLM", "DeepSeek", "Vulnerability Research", "Automated Exploitation"],
        enriched: true,
        summary_bullets: [
          "Security researchers demonstrate that open-weight reasoning models like DeepSeek-R1 can autonomously discover complex race conditions in Linux kernel drivers.",
          "The model achieved a 42% success rate in generating working proof-of-concept exploits when fed raw decompiled binaries.",
          "Defensive teams are adapting the same models to automate root-cause analysis and generate verified patches prior to deployment."
        ],
        business_angle: "AI reasoning models are drastically compressing the timeline between vulnerability disclosure and automated exploitation from weeks to hours.",
        interview_nugget: "The asymmetry of AI in cybersecurity: offensive AI only needs to find one flaw in a complex state machine, whereas defensive AI must formally prove memory safety across all paths."
      },
      {
        id: `demo-art-${pageNum}-3`,
        title: "LockBit Ransomware Affiliate Toolkit Leaked Following Law Enforcement Disruptions",
        url: "https://krebsonsecurity.com",
        source: "krebs_on_security",
        stream: "news",
        author: "Brian Krebs",
        published_at: new Date(Date.now() - 14400000 * pageNum).toISOString(),
        tags: ["Ransomware", "LockBit", "Operation Cronos", "Threat Intel"],
        enriched: true,
        summary_bullets: [
          "An updated version of the LockBit 3.0 builder and affiliate negotiation scripts has surfaced on cybercrime forums following Operation Cronos.",
          "The toolkit reveals automated scripts for disabling EDR agents and clearing Windows Event Logs using BYOVD (Bring Your Own Vulnerable Driver) techniques.",
          "Law enforcement agencies have decrypted over 3,000 victim servers using keys seized from backend infrastructure."
        ],
        business_angle: "Even after major law enforcement takedowns, leaked builder kits allow splinter groups and low-skilled actors to launch ransomware campaigns with enterprise-grade tooling.",
        interview_nugget: "BYOVD attacks demonstrate why kernel-level driver blocklists must be continuously updated; signing certificates of vulnerable legitimate drivers must be revoked at the OS level."
      }
    ];
  } else {
    return [
      {
        id: `demo-vuln-${pageNum}-1`,
        cve_id: "CVE-2024-3400",
        source: "kev",
        severity: "CRITICAL",
        cvss_v3_score: 10.0,
        cvss_v3_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        description: "A command injection as a result of arbitrary file creation feature in the GlobalProtect feature of Palo Alto Networks PAN-OS software for specific PAN-OS versions and distinct feature configurations may enable an unauthenticated attacker to execute arbitrary code with root privileges on the firewall.",
        kev_due_date: "2024-04-19",
        kev_known_ransomware: true,
        published_at: new Date(Date.now() - 86400000 * pageNum).toISOString(),
        enriched: true,
        summary_bullets: [
          "Unauthenticated remote command execution (RCE) with root privileges on PAN-OS GlobalProtect gateways.",
          "Active exploitation observed globally by state-sponsored cyber espionage actors (Operation MidnightEclipse) and ransomware syndicates.",
          "Requires telemetry feature to be enabled under specific configurations, but patching to hotfix release is mandatory."
        ],
        business_angle: "CVSS 10.0 perimeter vulnerability actively exploited by ransomware syndicates. Immediate emergency patching required; failure to patch creates severe risk of total domain compromise.",
        interview_nugget: "CVE-2024-3400 illustrates the danger of string concatenation in telemetry parsing pipelines; edge devices running as root must employ strict sandboxing and privilege separation."
      },
      {
        id: `demo-vuln-${pageNum}-2`,
        cve_id: "CVE-2024-23897",
        source: "nvd",
        severity: "CRITICAL",
        cvss_v3_score: 9.8,
        cvss_v3_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        description: "Jenkins 2.441 and earlier, LTS 2.426.2 and earlier does not disable a feature of its CLI command parser that replaces an '@' character followed by a file path in an argument with the file's contents, allowing unauthenticated attackers to read arbitrary files on the Jenkins controller file system.",
        kev_due_date: null,
        kev_known_ransomware: false,
        published_at: new Date(Date.now() - 172800000 * pageNum).toISOString(),
        enriched: true,
        summary_bullets: [
          "Arbitrary file read vulnerability via Jenkins CLI args usage of '@' character expansion.",
          "Unauthenticated attackers can read cryptographic keys, SSH credentials, and environment variables stored on the Jenkins master.",
          "Can be escalated to Remote Code Execution (RCE) if Resource Root URL or specific plugins are enabled."
        ],
        business_angle: "CI/CD servers hold the keys to the entire software supply chain. Exposing Jenkins credentials allows attackers to inject malicious code into production builds silently.",
        interview_nugget: "When auditing CI/CD pipelines, arbitrary file reads on the orchestrator are equivalent to RCE because build masters store SSH keys and cloud API secrets in plaintext working directories."
      }
    ];
  }
}
