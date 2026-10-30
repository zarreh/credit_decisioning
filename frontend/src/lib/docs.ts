// The MkDocs site (docs/). Overridable at build time (NEXT_PUBLIC_* is inlined into the bundle).
export const DOCS_URL = (process.env.NEXT_PUBLIC_DOCS_URL ?? "https://zarreh.github.io/credit_decisioning/").replace(
  /\/?$/,
  "/",
);
export const REPO_URL = "https://github.com/zarreh/credit_decisioning";

export const DOC_PAGES = {
  howItWorks: "how-it-works/",
  verifier: "how-it-works/verifier/",
  analyst: "how-it-works/analyst/",
  evidence: "evidence/",
  fairness: "evidence/fairness/",
  limits: "evidence/limits/",
  regulatoryBasis: "regulatory-basis/",
  caseStudy: "case-study/",
} as const;

export const docsLink = (page: keyof typeof DOC_PAGES) => `${DOCS_URL}${DOC_PAGES[page]}`;
