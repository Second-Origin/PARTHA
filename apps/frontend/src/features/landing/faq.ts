/** The landing page FAQ.
 *
 * The design's FAQ component set (Figma node 480:8100) exports three states:
 * every row closed, the first row open, and the second row open. So the first
 * two answers below are the design's own words, transcribed from those states.
 *
 * The remaining four answers have never been exported open, so their design
 * copy is unknown; what is here is earlier PARTHA wording, accurate to the
 * product but not verified against the canvas. Replace them once those states
 * are available. */

export const faqQuestions = [
  'Is PARTHA an AI product?',
  'How do you handle dynamic dispatch, reflection, and generated code?',
  'Which languages are supported?',
  'Where does PARTHA run?',
  'How does PARTHA integrate with our CI?',
  'What is the ri.v1 format?',
] as const;

export const faqAnswers = [
  // Transcribed from the design.
  'No. PARTHA is a deterministic extractor. There is no model that hallucinates and no temperature parameter. The same repo at the same revision produces a byte-identical ri.v1 artifact.',
  'They\u2019re flagged, not guessed. Each unresolved call site has a confidence field and provenance. You see exactly what PARTHA could and could not statically resolve.',
  // Not yet exported from the design; PARTHA wording, pending the real copy.
  'Language support is determined by the extractors available for the selected repository. The sealed snapshot records exactly what was assessed.',
  'PARTHA analyses a repository at a specific revision and retains a reproducible model for the workspace.',
  'Connect a repository, select a revision, then use the generated evidence and exports in the engineering workflow that suits your team.',
  'ri.v1 is PARTHA\u2019s sealed repository-intelligence snapshot format. It records the exact revision, extracted facts, and available evidence.',
] as const;
