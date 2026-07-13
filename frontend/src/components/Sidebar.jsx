
import React from 'react';

const STATUS_ICONS = {
  done: '●',
  failed: '✗',
  cloning: '...',
  pending: '○',
};

const STATUS_COLORS = {
  done: 'var(--green)',
  failed: 'var(--red)',
  cloning: 'var(--yellow)',
  pending: 'var(--text3)',
};

export default function Sidebar({ repos, activeId, onSelect }) {
  return (
    <div className="sidebar">
      <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'20px' }}>
        <span style={{ fontSize:'20px' }}>🍍</span>
        <span style={{ fontSize:'15px', fontWeight:600, color:'var(--text)' }}>pineapple</span>
      </div>
      <div className="sidebar-title">Recent Projects</div>
      <div className="repo-list">
        {repos.length === 0 && (
          <div style={{ padding:'16px 8px', fontSize:'13px', color:'var(--text3)', textAlign:'center' }}>
            No projects yet<br/>Clone a repo to get started
          </div>
        )}
        {repos.map(r => (
          <div
            key={r.id}
            className={'repo-item' + (r.id === activeId ? ' active' : '')}
            onClick={() => onSelect(r.id)}
          >
            <span className={'indicator ' + (r.clone_status || 'pending')} />
            <span className="repo-name">{r.name}</span>
            <span className="repo-time">
              {r.created_at ? r.created_at.slice(5, 16) : ''}
            </span>
          </div>
        ))}
      </div>
      <div style={{ marginTop:'auto', fontSize:'11px', color:'var(--text3)', padding:'8px' }}>
        {repos.length} project{repos.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
