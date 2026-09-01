const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';
const DISCORD_URL = 'https://discord.gg/qvk9DcxDA';

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-6 py-8 text-2xs text-muted-foreground sm:flex-row sm:px-8">
        <p>© {new Date().getFullYear()} PARTHA. Apache License 2.0.</p>
        <div className="flex items-center gap-5">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
            GitHub
          </a>
          <a href={DISCORD_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
            Discord
          </a>
          <a href={`${GITHUB_URL}/blob/dev/SECURITY.md`} target="_blank" rel="noreferrer" className="hover:text-foreground">
            Security
          </a>
        </div>
      </div>
    </footer>
  );
}
