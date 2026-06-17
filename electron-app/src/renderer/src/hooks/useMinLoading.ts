import { useEffect, useState } from 'react';

export const useMinLoading = (loading: boolean, minTime = 200) => {
  const [show, setShow] = useState(true);

  useEffect(() => {
    const start = Date.now();

    if (!loading) {
      const diff = Date.now() - start;
      const wait = Math.max(minTime - diff, 0);

      const t = setTimeout(() => setShow(false), wait);
      return () => clearTimeout(t);
    } else {
      setShow(true);
    }
  }, [loading, minTime]);

  return show;
};
