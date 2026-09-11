import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, RefreshCw } from 'lucide-react';
import { backendService } from '@/shared/services/backend';
import { getErrorMessage } from '@/shared/services/api';

interface RepositoryReanalyseButtonProps {
  repositoryId: string;
  /** Re-read the history in place once a new revision exists (#448). */
  onRevisionImported: () => void;
}

/* Bring a lineaged GitHub repository up to its branch head (#448).
 *
 * "Nothing has changed" is reported here as a state, not as a failure: before
 * this existed, the only way to ask was to retype the URL, and an unmoved
 * branch answered "Repository has already been imported", which reads as a
 * wall rather than as "you are already current". So the settled case gets a
 * plain, neutral sentence and the moved case navigates to what it found. */
export function RepositoryReanalyseButton({ repositoryId, onRevisionImported }: RepositoryReanalyseButtonProps) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await backendService.reanalyseRepository(repositoryId);
      if (result.outcome === 'already-current') {
        // The checked commit is named rather than implied: "up to date" with
        // nothing behind it asks the reader to take the check on trust.
        setMessage(`Already at ${result.remoteHead.slice(0, 12)} — nothing new to analyse.`);
        return;
      }
      onRevisionImported();
      navigate(`/repositories/${result.repository.id}`);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <button
        type="button"
        onClick={() => void run()}
        disabled={busy}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60"
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : (
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
        )}
        {busy ? 'Checking the branch…' : 'Check for a new revision'}
      </button>
      {/* Polite, not assertive: the outcome is information, and the settled
          case is the common one -- it should not interrupt a screen reader. */}
      <p role="status" aria-live="polite" className="text-xs text-muted-foreground">
        {message}
      </p>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
