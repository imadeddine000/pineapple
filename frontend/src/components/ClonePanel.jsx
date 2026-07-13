
import React, { useState, useRef, useEffect } from 'react';
import { useToast } from './Toast';

const API = (method, path, body) =>
  fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => r.json()).then(d => { if (d.error) throw new Error(d.error); return d; });

export default function ClonePanel({ onRepoCloned }) {
  const toast = useToast();
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('idle'); // idle | cloning | done | failed
  const [progress, setProgress] = useState(0);
  const [log, setLog] = useState('');
  const [cloningId, setCloningId] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startClone = async () => {
    if (!url.trim()) return;
    setStatus('cloning');
    setProgress(0);
    setLog('Starting clone...\n');

    try {
      const data = await API('POST', '/repos', { url: url.trim() });
      const repoId = data.id;
      setCloningId(repoId);

      pollRef.current = setInterval(async () => {
        try {
          const st = await API('GET', '/repos/' + repoId);
          if (st.clone_log) setLog(st.clone_log);
          if (st.clone_progress !== undefined) setProgress(st.clone_progress);

          if (st.clone_status === 'done') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus('done');
            setProgress(100);
            toast('Cloned "' + st.name + '"');
            if (onRepoCloned) onRepoCloned(repoId);
          } else if (st.clone_status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus('failed');
            setLog(prev => prev + '\nError: ' + (st.clone_error || 'Clone failed'));
            toast('Clone failed');
          }
        } catch (e) {}
      }, 800);
    } catch (err) {
      setStatus('failed');
      setLog(prev => prev + '\nError: ' + err.message);
      toast(err.message);
    }
  };

  return (
    <div className="card">
      <div className="card-title">Clone Repository</div>
      <div className="input-row">
        <span style={{ fontSize:'16px', color:'var(--text3)' }}>🔗</span>
        <input
          type="text"
          placeholder="https://github.com/user/repo"
          value={url}
          onChange={e => setUrl(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && startClone()}
          disabled={status === 'cloning'}
        />
        <button className="btn btn-primary" onClick={startClone} disabled={status === 'cloning' || !url.trim()}>
          {status === 'cloning' ? <><span className="spinner" /> Cloning</> : 'Clone'}
        </button>
      </div>

      {(status === 'cloning' || status === 'done' || status === 'failed') && (
        <>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: progress + '%' }} />
          </div>
          <div style={{ fontSize:'12px', color:'var(--text3)', marginBottom:'4px' }}>
            {status === 'cloning' ? 'Cloning... ' + Math.round(progress) + '%' :
             status === 'done' ? '✓ Cloned successfully' :
             '✗ Clone failed'}
          </div>
          {log && <div className="clone-log">{log}</div>}
        </>
      )}
    </div>
  );
}
