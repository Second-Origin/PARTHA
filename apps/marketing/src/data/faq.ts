/** The landing page FAQ, shared by the desktop overlay's dialog (App.tsx) and
 * the mobile/tablet accordion (MobileLanding.tsx). Wording matches the
 * authored design canvas. */

export const faqQuestions = [
  'Is PARTHA an AI product?',
  'How do you handle dynamic dispatch, reflection, and generated code?',
  'Which languages are supported?',
  'Where does PARTHA run?',
  'How does PARTHA integrate with our CI?',
  'What is the ri.v1 format?',
] as const;

export const faqAnswers = [
  'PARTHA creates deterministic, evidence-backed repository models. AI assistance is optional and is limited to structural facts that have already been computed from a sealed snapshot.',
  'PARTHA makes supported evidence and limits visible. Findings that cannot be verified from the selected revision are not presented as facts.',
  'Language support is determined by the extractors available for the selected repository. The sealed snapshot records exactly what was assessed.',
  'PARTHA analyses a repository at a specific revision and retains a reproducible model for the workspace.',
  'Connect a repository, select a revision, then use the generated evidence and exports in the engineering workflow that suits your team.',
  'ri.v1 is PARTHA’s sealed repository-intelligence snapshot format. It records the exact revision, extracted facts, and available evidence.',
] as const;
