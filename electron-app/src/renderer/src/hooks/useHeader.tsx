import { useEffect, useState } from 'react';
import api from '../api/client';


export const useAuth = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);


  const fetchMe = async () => {
    try {
      const res = await api.get('/auth/me');

      setUser(res.data.user);
    } catch (e) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMe();
  }, []);


  return { user, loading };
};