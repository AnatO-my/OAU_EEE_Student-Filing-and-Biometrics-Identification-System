import { useEffect, useState } from 'react';

export function useRemote(load, identity) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.resolve().then(() => load(controller.signal)).then(data => {
      if (!controller.signal.aborted) setState({ load, identity, attempt, data, error: null });
    }).catch(error => {
      if (!controller.signal.aborted) setState({ load, identity, attempt, data: null, error });
    });
    return () => controller.abort();
  }, [load, identity, attempt]);
  const current = state?.load === load && state?.identity === identity && state?.attempt === attempt;
  return { data: current ? state.data : null, error: current ? state.error : null,
    loading: !current, retry: () => setAttempt(value => value + 1) };
}
