import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import InfiniteTimeline from './components/InfiniteTimeline';
import ChatPanel from './components/ChatPanel';
import AuthModal from './components/AuthModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('cyberintel_theme') || 'orange';
  });
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('cyberintel_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Global Dashboard Data
  const [articles, setArticles] = useState([]);
  const [vulns, setVulns] = useState([]);
  const [stats, setStats] = useState({
    totalArticles: 142,
    totalVulns: 318,
    kevCount: 24,
    criticalHighCount: 89,
    enrichedPercentage: '98.5%'
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('cyberintel_theme', theme);
  }, [theme]);

  // Fetch dashboard preview data
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [artRes, vulnRes] = await Promise.all([
          fetch('/api/articles?page=1&page_size=6').catch(() => null),
          fetch('/api/vulnerabilities?page=1&page_size=6').catch(() => null)
        ]);

        if (artRes?.ok) {
          const artData = await artRes.json();
          setArticles(artData.items || []);
          if (artData.total) setStats(prev => ({ ...prev, totalArticles: artData.total }));
        } else {
          // Use demo fallback if API not running locally
          setArticles(getMockArticles());
        }

        if (vulnRes?.ok) {
          const vulnData = await vulnRes.json();
          setVulns(vulnData.items || []);
          if (vulnData.total) setStats(prev => ({ ...prev, totalVulns: vulnData.total }));
        } else {
          setVulns(getMockVulns());
        }
      } catch (err) {
        console.warn('Dashboard fetch error, using local demo data:', err);
        setArticles(getMockArticles());
        setVulns(getMockVulns());
      }
    };

    loadDashboardData();
  }, []);

  const handleLoginSuccess = (userProfile, token) => {
    setUser(userProfile);
  };

  const handleLogout = () => {
    localStorage.removeItem('cyberintel_token');
    localStorage.removeItem('cyberintel_user');
    setUser(null);
  };

  return (
    <>
      <Layout
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        theme={theme}
        setTheme={setTheme}
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        onLogout={handleLogout}
      >
        {activeTab === 'dashboard' && (
          <Dashboard
            articles={articles}
            vulns={vulns}
            stats={stats}
            onNavigate={(tab) => {
              if (tab === 'vulnerabilities') {
                setActiveTab('vulnerabilities');
              } else if (tab === 'timeline') {
                setActiveTab('timeline');
              } else if (tab === 'chat') {
                setActiveTab('chat');
              }
            }}
          />
        )}

        {activeTab === 'timeline' && (
          <InfiniteTimeline activeTab="articles" setActiveTab={(tab) => setActiveTab(tab === 'vulns' ? 'vulnerabilities' : 'timeline')} />
        )}

        {activeTab === 'vulnerabilities' && (
          <InfiniteTimeline activeTab="vulns" setActiveTab={(tab) => setActiveTab(tab === 'vulns' ? 'vulnerabilities' : 'timeline')} />
        )}

        {activeTab === 'chat' && (
          <ChatPanel />
        )}
      </Layout>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onLoginSuccess={handleLoginSuccess}
      />
    </>
  );
}

// Mock fallback generator when backend is not running locally
function getMockArticles() {
  return [
    {
      id: "demo-1",
      title: "Critical Zero-Day Exploited in Ivanti Connect Secure VPN Gateways",
      url: "https://thehackernews.com",
      source: "the_hacker_news",
      stream: "news",
      author: "Ravie Lakshmanan",
      published_at: new Date().toISOString(),
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
      id: "demo-2",
      title: "DeepSeek-R1 AI Architecture Analyzed for Novel Automated Exploit Generation",
      url: "https://darkreading.com",
      source: "darkreading",
      stream: "research",
      author: "Kelly Jackson Higgins",
      published_at: new Date(Date.now() - 7200000).toISOString(),
      tags: ["LLM", "DeepSeek", "Vulnerability Research", "Automated Exploitation"],
      enriched: true,
      summary_bullets: [
        "Security researchers demonstrate that open-weight reasoning models like DeepSeek-R1 can autonomously discover complex race conditions in Linux kernel drivers.",
        "The model achieved a 42% success rate in generating working proof-of-concept exploits when fed raw decompiled binaries.",
        "Defensive teams are adapting the same models to automate root-cause analysis and generate verified patches prior to deployment."
      ],
      business_angle: "AI reasoning models are drastically compressing the timeline between vulnerability disclosure and automated exploitation from weeks to hours.",
      interview_nugget: "The asymmetry of AI in cybersecurity: offensive AI only needs to find one flaw in a complex state machine, whereas defensive AI must formally prove memory safety across all paths."
    }
  ];
}

function getMockVulns() {
  return [
    {
      id: "demo-vuln-1",
      cve_id: "CVE-2024-3400",
      source: "kev",
      severity: "CRITICAL",
      cvss_v3_score: 10.0,
      cvss_v3_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
      description: "A command injection as a result of arbitrary file creation feature in the GlobalProtect feature of Palo Alto Networks PAN-OS software for specific PAN-OS versions and distinct feature configurations may enable an unauthenticated attacker to execute arbitrary code with root privileges on the firewall.",
      kev_due_date: "2024-04-19",
      kev_known_ransomware: true,
      published_at: new Date().toISOString(),
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
      id: "demo-vuln-2",
      cve_id: "CVE-2024-23897",
      source: "nvd",
      severity: "CRITICAL",
      cvss_v3_score: 9.8,
      cvss_v3_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
      description: "Jenkins 2.441 and earlier, LTS 2.426.2 and earlier does not disable a feature of its CLI command parser that replaces an '@' character followed by a file path in an argument with the file's contents, allowing unauthenticated attackers to read arbitrary files on the Jenkins controller file system.",
      kev_due_date: null,
      kev_known_ransomware: false,
      published_at: new Date(Date.now() - 172800000).toISOString(),
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
