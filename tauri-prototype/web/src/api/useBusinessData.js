import { useCallback, useEffect, useRef, useState } from 'react';

export function useBusinessData(loader) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const requestId = useRef(0);

  const refresh = useCallback(async () => {
    const currentRequestId = ++requestId.current;
    setLoading(true);
    setError('');
    try {
      const result = await loader();
      if (currentRequestId === requestId.current) setData(result);
      return result;
    } catch (failure) {
      if (currentRequestId === requestId.current) {
        setError(failure.message || 'Impossible de charger les données métier.');
      }
      throw failure;
    } finally {
      if (currentRequestId === requestId.current) setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    setData(null);
    refresh().catch(() => {});
    return () => {
      requestId.current += 1;
    };
  }, [refresh]);

  return { data, loading, error, refresh };
}
