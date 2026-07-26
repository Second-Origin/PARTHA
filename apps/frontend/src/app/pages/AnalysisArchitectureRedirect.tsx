import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAppStore } from '@/app/store/useAppStore';

// A repository-scoped deep link into Architecture (#179): the surface itself
// is only ever mounted at the top-level `/architecture` route and reads the
// globally selected repository, so this selects the requested repository
// first and hands off to that route rather than duplicating the surface.
export function AnalysisArchitectureRedirect() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const setActiveRepositoryId = useAppStore((state) => state.setActiveRepositoryId);

  useEffect(() => {
    if (id) setActiveRepositoryId(id);
    navigate('/architecture', { replace: true });
  }, [id, navigate, setActiveRepositoryId]);

  return null;
}
