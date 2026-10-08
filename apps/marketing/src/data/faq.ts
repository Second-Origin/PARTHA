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
  'Structural extraction does not use an AI model. Equal revision, schema, producer versions, and output configuration produce the same canonical graph hash. Snapshot UUIDs and export timestamps vary; optional AI answers are generated and are not automatically cited.',
  'Recognized unsupported constructs and unresolved relationships produce diagnostics with available provenance. Detection is incomplete for dynamic dispatch, reflection, and generated code. Unresolved call observations do not each carry a confidence field.',
  // Not yet exported from the design; PARTHA wording, pending the real copy.
  'Language support is determined by the extractors available for the selected repository. The sealed snapshot records exactly what was assessed.',
  'PARTHA analyses a repository at a specific revision and retains a reproducible model for the workspace.',
  'Connect a repository, select a revision, then use the generated evidence and exports in the engineering workflow that suits your team.',
  'ri.v1 is the sealed repository-intelligence snapshot format. Supported evidence-backed facts include exact provenance; inventory and heuristic classification have different evidence contracts. The canonical graph hash identifies graph content, independently of snapshot UUIDs and export metadata. Exports are unsigned.',
] as const;
