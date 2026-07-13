
import React from 'react';
import { useToast } from './Toast';

export default function DockerfilePreview({ dockerfile }) {
  const toast = useToast();
  if (!dockerfile) return null;
  const lines = dockerfile.split('\n').length;
  const copy = () => {
    navigator.clipboard.writeText(dockerfile).then(() => toast('Copied to clipboard')).catch(() => {});
  };
  return (
    <div className="card">
      <div className="code-toolbar">
        <span className="code-toolbar-label">Dockerfile</span>
        <div style={{ display:'flex', gap:'8px', alignItems:'center' }}>
          <span style={{ fontSize:'12px', color:'var(--text3)' }}>{lines} lines / {dockerfile.length} chars</span>
          <button className="btn btn-ghost btn-sm" onClick={copy}>📋 Copy</button>
        </div>
      </div>
      <div className="code-block">{dockerfile}</div>
    </div>
  );
}
