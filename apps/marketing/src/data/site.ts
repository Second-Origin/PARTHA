/** Single source of truth for the landing page's external destinations and
 * footer structure. The desktop overlay (App.tsx) derives its positioned
 * hotspot list from FOOTER_COLUMNS; the mobile/tablet layout
 * (MobileLanding.tsx) renders the columns directly. */

export const GITHUB_URL = 'https://github.com/Second-Origin/PARTHA';
const REPO_BLOB = `${GITHUB_URL}/blob/dev`;
export const DISCORD_URL = 'https://discord.gg/qvk9DcxDA';
export const LINKEDIN_URL = 'https://www.linkedin.com/in/parthrohit';

export type FooterLink = {
  label: string;
  href: string;
  /** true opens in a new tab (rel=noreferrer); false is a same-page anchor. */
  external: boolean;
};

export const FOOTER_COLUMNS: { heading: string; links: FooterLink[] }[] = [
  {
    heading: 'Product',
    links: [
      { label: 'How it works', href: '#how-it-works', external: false },
      { label: 'Capabilities', href: '#capabilities', external: false },
      { label: 'FAQ', href: '#faq', external: false },
      { label: 'Privacy', href: `${REPO_BLOB}/README.md#current-limitations`, external: true },
    ],
  },
  {
    heading: 'Resources',
    links: [
      { label: 'Docs', href: `${REPO_BLOB}/docs/README.md`, external: true },
      { label: 'ri.v1 spec', href: `${REPO_BLOB}/docs/architecture/REPOSITORY_INTELLIGENCE_V1_RFC.md`, external: true },
      {
        label: 'Language matrix',
        href: `${REPO_BLOB}/docs/architecture/REPOSITORY_INTELLIGENCE.md#what-is-currently-extracted`,
        external: true,
      },
      { label: 'Changelog', href: `${GITHUB_URL}/releases`, external: true },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'About', href: `${REPO_BLOB}/README.md`, external: true },
      { label: 'Security', href: `${REPO_BLOB}/SECURITY.md`, external: true },
      { label: 'Contact', href: DISCORD_URL, external: true },
      { label: 'Legal', href: `${REPO_BLOB}/LICENSE`, external: true },
    ],
  },
  {
    heading: 'Connect',
    links: [
      { label: 'LinkedIn', href: LINKEDIN_URL, external: true },
      { label: 'X', href: DISCORD_URL, external: true },
      { label: 'GitHub', href: GITHUB_URL, external: true },
    ],
  },
];
