import type { ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders analyst-written Markdown (bold, lists, tables, headings, code).
 *
 * react-markdown renders raw HTML as text, never as elements, and we do not enable the raw-HTML
 * plugin, so model output cannot inject markup. Links open in a new tab and are limited to
 * http(s)/mailto by the library's default URL filter.
 */
const components: ComponentProps<typeof ReactMarkdown>["components"] = {
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900 dark:text-white">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  h1: ({ children }) => <h3 className="mb-1 mt-4 text-base font-semibold text-slate-900 first:mt-0 dark:text-white">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-1 mt-4 text-base font-semibold text-slate-900 first:mt-0 dark:text-white">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-slate-900 first:mt-0 dark:text-white">{children}</h4>,
  h4: ({ children }) => <h4 className="mb-1 mt-3 text-sm font-semibold text-slate-900 first:mt-0 dark:text-white">{children}</h4>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-teal-400 pl-3 text-slate-600 dark:text-slate-300">{children}</blockquote>
  ),
  code: ({ children }) => (
    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] dark:bg-slate-800">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-slate-100 p-3 text-xs dark:bg-slate-800">{children}</pre>
  ),
  // The library blanks unsafe URLs (javascript:, data:); render those as plain text, not a dead link.
  a: ({ href, children }) =>
    href ? (
      <a href={href} target="_blank" rel="noreferrer noopener" className="font-medium text-teal-700 underline dark:text-teal-400">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  hr: () => <hr className="my-3 border-slate-200 dark:border-slate-700" />,
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-slate-300 px-2 py-1 font-semibold dark:border-slate-600">{children}</th>,
  td: ({ children }) => <td className="border-b border-slate-100 px-2 py-1 dark:border-slate-800">{children}</td>,
};

export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm leading-relaxed text-slate-800 dark:text-slate-200">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
