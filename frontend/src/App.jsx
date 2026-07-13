import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const API = (method, path, body) =>
  fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => r.json()).then(d => { if (d.error) throw new Error(d.error); return d; });

function App() {
  const [page, setPage] = useState('projects');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [toasts, setToasts] = useState([]);

  const toast = (msg) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, msg }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000);
  };

  const loadProjects = useCallback(async () => {
    try {
      const data = await API('GET', '/projects');
      setProjects(data.projects || []);
    } catch (e) {}
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const addToast = (msg) => toast(msg);

  return (
    <div className="app-layout">
      <div className="sidebar">
        <div className="sidebar-logo" onClick={() => setPage('projects')}>
          <span className="logo-icon">\U0001f34d</span>
          <span className="logo-text">pineapple</span>
        </div>
        <div className="sidebar-nav">
          <div
            className={'nav-item' + (page === 'projects' || page === 'project-detail' ? ' active' : '')}
            onClick={() => { setPage('projects'); setSelectedProject(null); }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
            <span>Projects</span>
          </div>
          <div
            className={'nav-item' + (page === 'new-project' ? ' active' : '')}
            onClick={() => setPage('new-project')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>New Project</span>
          </div>
          <div
            className={'nav-item' + (page === 'settings' ? ' active' : '')}
            onClick={() => setPage('settings')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
            <span>Settings</span>
          </div>
        </div>
      </div>

      <div className="main-content">
        {page === 'projects' && (
          <ProjectsPage
            projects={projects}
            onSelect={(p) => { setSelectedProject(p); setPage('project-detail'); }}
            onNew={() => setPage('new-project')}
            onRefresh={loadProjects}
            toast={addToast}
          />
        )}
        {page === 'new-project' && (
          <NewProjectPage
            onCreated={() => { loadProjects(); setPage('projects'); }}
            toast={addToast}
          />
        )}
        {page === 'settings' && (
          <SettingsPage toast={addToast} />
        )}
        {page === 'project-detail' && selectedProject && (
          <ProjectDetailPage
            project={selectedProject}
            onBack={() => { setSelectedProject(null); setPage('projects'); loadProjects(); }}
            toast={addToast}
          />
        )}
      </div>

      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className="toast">{t.msg}</div>
        ))}
      </div>
    </div>
  );
}

/* ── Projects Page ── */
function ProjectsPage({ projects, onSelect, onNew, onRefresh, toast }) {
  useEffect(() => { onRefresh(); }, []);
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">Manage your container builds</p>
        </div>
        <button className="btn btn-primary" onClick={onNew}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Project
        </button>
      </div>
      {projects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">\U0001f4c1</div>
          <h3>No projects yet</h3>
          <p>Create your first project to get started.</p>
          <button className="btn btn-primary" onClick={onNew} style={{marginTop:16}}>Create Project</button>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map(p => (
            <div key={p.id} className="project-card" onClick={() => onSelect(p)}>
              <div className="project-card-header">
                <div className="project-icon">{p.name.charAt(0).toUpperCase()}</div>
                <div className="project-info">
                  <div className="project-name">{p.name}</div>
                  <div className="project-desc">{p.description || 'No description'}</div>
                </div>
              </div>
              <div className="project-card-footer">
                <span className={'status-badge ' + (p.repo_status || 'pending')}>
                  {p.repo_status === 'done' ? '\u2713 Ready' :
                   p.repo_status === 'cloning' ? 'Cloning' :
                   p.repo_status === 'failed' ? '\u2717 Failed' : 'Pending'}
                </span>
                <span className="project-date">{p.created_at ? p.created_at.slice(0, 10) : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── New Project Page ── */
function NewProjectPage({ onCreated, toast }) {
  const [tab, setTab] = useState('github');
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [repos, setRepos] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [cloning, setCloning] = useState(false);

  useEffect(() => {
    API('GET', '/github/accounts').then(d => setAccounts(d.accounts || [])).catch(() => {});
  }, []);

  const loadRepos = async (accountId) => {
    setLoadingRepos(true);
    setSelectedAccount(accountId);
    setRepos([]);
    try {
      const data = await API('GET', '/github/accounts/' + accountId + '/repos');
      setRepos(data.repos || []);
    } catch (e) { toast('Error: ' + e.message); }
    setLoadingRepos(false);
  };

  const filteredRepos = repos.filter(r =>
    !searchQuery || r.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const importRepo = async (ghRepo) => {
    setCloning(true);
    try {
      const repo = await API('POST', '/repos', { url: ghRepo.clone_url });
      await API('POST', '/projects', { name: ghRepo.name, repo_id: repo.id });
      toast('Imported: ' + ghRepo.name);
      onCreated();
    } catch (e) { toast('Error: ' + e.message); }
    setCloning(false);
  };

  const createFromUrl = async () => {
    if (!url.trim() || !name.trim()) { toast('Enter URL and name'); return; }
    setCloning(true);
    try {
      const repo = await API('POST', '/repos', { url: url.trim() });
      await API('POST', '/projects', { name: name.trim(), repo_id: repo.id });
      toast('Created: ' + name);
      onCreated();
    } catch (e) { toast('Error: ' + e.message); }
    setCloning(false);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">New Project</h1>
          <p className="page-subtitle">Import from GitHub or paste a URL</p>
        </div>
      </div>
      <div className="tabs">
        <div className={'tab ' + (tab === 'github' ? ' active' : '')} onClick={() => setTab('github')}>From GitHub</div>
        <div className={'tab ' + (tab === 'url' ? ' active' : '')} onClick={() => setTab('url')}>From URL</div>
      </div>
      <div className="card" style={{marginTop:0}}>
        {tab === 'github' && (
          <>
            {accounts.length === 0 ? (
              <div style={{padding:24,textAlign:'center',color:'var(--text3)'}}>
                <p>No GitHub accounts connected.</p>
                <p style={{fontSize:13,marginTop:8}}>Run: <code style={{background:'var(--bg2)',padding:'2px 6px',borderRadius:3}}>pineapple github connect</code></p>
              </div>
            ) : (
              <>
                <div className="form-group">
                  <label className="form-label">Account</label>
                  <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                    {accounts.map(a => (
                      <div key={a.id}
                        className={'gitignore-tag' + (selectedAccount === a.id ? ' active' : '')}
                        onClick={() => loadRepos(a.id)}>
                        {a.account_name}
                      </div>
                    ))}
                  </div>
                </div>
                {selectedAccount && (
                  <div className="form-group">
                    <label className="form-label">Search</label>
                    <input className="form-input" placeholder="Search repos..." value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)} />
                  </div>
                )}
                {loadingRepos && <div style={{padding:24,textAlign:'center',color:'var(--text3)'}}>Loading...</div>}
                {!loadingRepos && selectedAccount && (
                  <div className="github-repo-list">
                    {filteredRepos.length === 0 && (
                      <div style={{padding:24,textAlign:'center',color:'var(--text3)'}}>No repos</div>
                    )}
                    {filteredRepos.map(r => (
                      <div key={r.id} className="github-repo-item" onClick={() => importRepo(r)}>
                        <div className="github-repo-left">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22"/></svg>
                          <div>
                            <div className="github-repo-name">{r.full_name}</div>
                            <div className="github-repo-desc">{r.description || r.language || ''}</div>
                          </div>
                        </div>
                        <div className="github-repo-right">
                          {r.private && <span className="badge-private">Private</span>}
                          <span className="github-repo-lang">{r.language || ''}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
        {tab === 'url' && (
          <>
            <div className="form-group"><label className="form-label">URL</label><input className="form-input" placeholder="https://github.com/user/repo.git" value={url} onChange={e => setUrl(e.target.value)} /></div>
            <div className="form-group"><label className="form-label">Name</label><input className="form-input" placeholder="my-project" value={name} onChange={e => setName(e.target.value)} /></div>
            <button className="btn btn-primary" onClick={createFromUrl} disabled={cloning || !url || !name}>
              {cloning ? 'Creating...' : 'Create Project'}
            </button>
          </>
        )}
        {cloning && <div style={{padding:12,textAlign:'center',color:'var(--text2)',marginTop:8}}>Working...</div>}
      </div>
    </div>
  );
}

/* ── Settings Page ── */
function SettingsPage({ toast }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Pineapple configuration</p>
        </div>
      </div>
      <div className="card">
        <div className="card-title">About</div>
        <p style={{fontSize:14,color:'var(--text2)',lineHeight:1.6}}>
          Pineapple detects frameworks, generates Dockerfiles, and builds container images.
        </p>
      </div>
      <div className="card">
        <div className="card-title">GitHub Integration</div>
        <p style={{fontSize:13,color:'var(--text2)',lineHeight:1.6}}>
          Use the CLI to connect your GitHub accounts:
        </p>
        <pre style={{background:'var(--bg2)',padding:'12px 16px',borderRadius:'var(--radius-sm)',fontFamily:'var(--mono)',fontSize:13,color:'var(--text)',marginTop:8,lineHeight:1.8}}>
          $ pineapple github setup{'\n'}
          $ pineapple github connect
        </pre>
      </div>
    </div>
  );
}

/* ── Project Detail Page ── */
function ProjectDetailPage({ project, onBack, toast }) {
  const [data, setData] = useState(null);
  const [dockerfile, setDockerfile] = useState(null);
  const [buildLog, setBuildLog] = useState('');
  const [buildStatus, setBuildStatus] = useState('idle');

  useEffect(() => {
    if (project.repo_id) {
      API('GET', '/repos/' + project.repo_id).then(setData).catch(() => {});
    }
  }, [project.repo_id]);

  const repo = data?.repo || {};
  const detection = data?.detection;
  const hasClone = repo.clone_status === 'done';

  return (
    <div>
      <div className="page-header">
        <div style={{display:'flex',alignItems:'center',gap:12}}>
          <button className="btn btn-ghost" onClick={onBack}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          </button>
          <div>
            <h1 className="page-title">{project.name}</h1>
            <p className="page-subtitle">{project.description || 'Project details'}</p>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Status</div>
        <div className="detection-grid">
          <div className="detection-item">
            <div className="detection-label">Status</div>
            <div className="detection-value">
              {repo.clone_status === 'done' ? '\u2713 Ready' :
               repo.clone_status === 'cloning' ? 'Cloning...' :
               repo.clone_status === 'failed' ? '\u2717 Failed' : 'Pending'}
            </div>
          </div>
          <div className="detection-item">
            <div className="detection-label">Repository</div>
            <div className="detection-value" style={{fontSize:13}}>{project.name}</div>
          </div>
          {detection && (
            <>
              <div className="detection-item"><div className="detection-label">Framework</div><div className="detection-value">{detection.framework}</div></div>
              <div className="detection-item"><div className="detection-label">Language</div><div className="detection-value">{detection.language}</div></div>
              <div className="detection-item"><div className="detection-label">Port</div><div className="detection-value">{detection.port}</div></div>
              <div className="detection-item"><div className="detection-label">Package Manager</div><div className="detection-value">{detection.package_manager}</div></div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Actions</div>
        <div className="actions-row" style={{marginBottom:12}}>
          <button className="btn btn-primary" disabled={!hasClone}
            onClick={async () => {
              try {
                const d = await API('POST', '/repos/' + project.repo_id + '/detect');
                setData(prev => ({...prev, detection: d.detection}));
                toast('Detection complete');
              } catch (e) { toast(e.message); }
            }}
          >Scan</button>
          <button className="btn btn-secondary" disabled={!hasClone}
            onClick={async () => {
              try {
                const d = await API('POST', '/repos/' + project.repo_id + '/generate');
                setDockerfile(d.dockerfile);
                toast('Dockerfile generated');
              } catch (e) { toast(e.message); }
            }}
          >Generate Dockerfile</button>
          <button className="btn btn-secondary" disabled={!hasClone}
            onClick={async () => {
              setBuildStatus('building');
              setBuildLog('Starting...\\n');
              try {
                const d = await API('POST', '/repos/' + project.repo_id + '/build', { tag: project.name + ':latest' });
                const poll = setInterval(async () => {
                  try {
                    const b = await API('GET', '/builds/' + d.id);
                    if (b.log) setBuildLog(b.log);
                    if (b.status === 'done') { clearInterval(poll); setBuildStatus(b.success ? 'success' : 'failed'); toast(b.success ? 'Build succeeded' : 'Build failed'); }
                  } catch (e) {}
                }, 600);
              } catch (e) { toast(e.message); setBuildStatus('failed'); }
            }}
          >Build Image</button>
        </div>
        {repo.clone_status === 'cloning' && (
          <>
            <div className="progress-bar" style={{marginBottom:8}}><div className="progress-fill" style={{width: (repo.clone_progress || 0) + '%'}} /></div>
            <div className="clone-log">{repo.clone_log || 'Cloning...'}</div>
          </>
        )}
        {buildStatus !== 'idle' && (
          <>
            <div className="code-toolbar" style={{marginTop:12}}>
              <span className="code-toolbar-label">Build Log</span>
              <span style={{color: buildStatus === 'success' ? 'var(--green)' : buildStatus === 'failed' ? 'var(--red)' : 'var(--text3)', fontSize:12}}>
                {buildStatus === 'success' ? '\u2713 Success' : buildStatus === 'failed' ? '\u2717 Failed' : 'Running...'}
              </span>
            </div>
            <div className="build-log">{buildLog || 'Waiting...'}</div>
          </>
        )}
      </div>

      {dockerfile && (
        <div className="card">
          <div className="code-toolbar">
            <span className="code-toolbar-label">Dockerfile</span>
            <button className="btn btn-ghost btn-sm" onClick={() => { navigator.clipboard.writeText(dockerfile).then(() => toast('Copied')).catch(() => {}); }}>Copy</button>
          </div>
          <div className="code-block">{dockerfile}</div>
        </div>
      )}
    </div>
  );
}

export default App;
