
import React from 'react';

export default function DetectionCard({ detection }) {
  if (!detection) return null;
  const items = [
    { label: 'Framework', value: detection.framework || 'unknown' },
    { label: 'Type', value: detection.type || 'unknown' },
    { label: 'Language', value: detection.language || 'unknown' },
    { label: 'Port', value: detection.port || '-' },
    { label: 'Package Manager', value: detection.package_manager || '-' },
  ];
  return (
    <div className="card">
      <div className="card-title">Detection</div>
      <div className="detection-grid">
        {items.map(i => (
          <div key={i.label} className="detection-item">
            <div className="detection-label">{i.label}</div>
            <div className="detection-value">{String(i.value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
