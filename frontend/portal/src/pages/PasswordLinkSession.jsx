import { Fragment, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

function readLink(location, allowQuery) {
  const fromFragment = !!location.hash;
  const params = new URLSearchParams(fromFragment ? location.hash.slice(1) : allowQuery ? location.search : '');
  const source = fromFragment ? location.hash : allowQuery && (params.has('uid') || params.has('token')) ? location.search : '';
  return { source, credentials: { uid: params.get('uid'), token: params.get('token') } };
}

// New links key a new form. URL cleanup keeps the current form and credentials;
// neither setup nor legacy reset credentials are kept in browser storage.
export default function PasswordLinkSession({ children, allowQuery = false }) {
  const location = useLocation(), navigate = useNavigate();
  const incoming = readLink(location, allowQuery);
  const [capture, setCapture] = useState(() => ({ ...incoming, generation: 0 }));
  if (incoming.source && incoming.source !== capture.source) {
    setCapture({ ...incoming, generation: capture.generation + 1 });
  } else if (!incoming.source && capture.source) {
    setCapture({ ...capture, source: '' });
  }
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (!location.hash && !query.has('uid') && !query.has('token')) return;
    query.delete('uid'); query.delete('token');
    const remaining = query.toString();
    navigate(`${location.pathname}${remaining ? `?${remaining}` : ''}`, { replace: true });
  }, [location.hash, location.pathname, location.search, navigate]);
  function consumed(expectedGeneration) {
    setCapture((current) => current.generation === expectedGeneration ? { ...current, credentials: { uid: null, token: null } } : current);
  }
  return <Fragment key={capture.generation}>{children(capture.credentials, () => consumed(capture.generation))}</Fragment>;
}
