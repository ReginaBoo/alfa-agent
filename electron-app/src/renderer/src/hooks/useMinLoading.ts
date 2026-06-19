import { useEffect, useState } from 'react';

export const useMinLoading = (loading: boolean, minTime = 200): boolean => {
  const [show, setShow] = useState(true);

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;

    if (!loading) {
      timer = setTimeout(() => {
        setShow(false);
      }, minTime);
    } else {
      setShow(true);
    }

    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [loading, minTime]);

  return show;
};
