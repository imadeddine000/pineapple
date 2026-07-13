
import React, { useState, useRef, useEffect } from 'react';
import { useToast } from './Toast';

const API = (method, path, body) =>
  fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => r.json());

export default function BuildLog({ repoId, localPath, detection }) {
  const toast = useToast();
  const [log, setLog] = useState('');
  const [status, setStatus] = useState('idle');
  const [buildId, setBuildId] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const startBuild = async () => {
    if (!repoId || !localPath) return;
    const tag = localPath.split('/').pop() + ':latest';
    setStatus('building');
    setLog('Starting build...\n');

    try {
      const data = await API('POST', '/repos/' + repoId + '/build', { tag });
      setBuildId(data.id);

      pollRef.current = setInterval(async () => {
        try {
          const b = await API('GET', '/builds/' + data.id);
          if (b.log) setLog(b.log);
          if (b.status === 'done') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus(b.success ? 'success' : 'failed');
            toast(b.success ? 'Build successful' : 'Build failed');
          } else if (b.status === 'failed') {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus('failed');
            toast('Build failed');
          }
        } catch (e) {}
      }, 600);
    } catch (err) {
      setLog(prev => prev + '\nError: ' + err.message);
      setStatus('failed');
    }
  };

  const hasBuild = status !== 'idle';

  return (
    <>
      <div className="card">
        <div className="card-title">Actions</div>
        <div className="actions-row">
          <button
            className="btn btn-primary"
            onClick={async () => {
              try {
                const data = await API('POST', '/repos/' + repoId + '/detect');
                if (data.detection) {
                  Object.assign(detection, data.detection);
                  window.dispatchEvent(new CustomEvent('detection-updated'));
                  toast('Detected: ' + data.detection.framework);
                }
              } catch (err) { toast(err.message); }
            }}
            disabled={!repoId}
          >
            Scan
          </button>
          <button
            className="btn btn-secondary"
            onClick={async () => {
              try {
                const data = await API('POST', '/repos/' + repoId + '/generate');
                if (data.dockerfile) {
                  window.dispatchEvent(new CustomEvent('dockerfile-updated', { detail: data.dockerfile }));
                  toast('Dockerfile generated');
                }
              } catch (err) { toast(err.message); }
            }}
            disabled={!repoId}
          >
            Generate Dockerfile
          </button>
          <button
            className="btn btn-secondary"
            onClick={startBuild}
            disabled={!repoId || status === 'building'}
          >
            {status === 'building' ? <><span className="spinner" /> Building</> : 'Build Image'}
          </button>
        </div>
      </div>

      {hasBuild && (
        <div className="card">
          <div className="code-toolbar">
            <span className="code-toolbar-label">Build Log</span>
            <span style={{ fontSize:'12px', color:
              status === 'success' ? 'var(--green)' :
              status === 'failed' ? 'var(--red)' :
              'var(--text3)'
            }}>
              {status === 'success' ? '✓ success' :
               status === 'failed' ? '✗ failed' :
               status === 'building' ? 'running' : ''}
            </span>
          </div>
          <div className="build-log">{log || 'No output yet...'}</div>
        </div>
      )}
    </>
  );
}
