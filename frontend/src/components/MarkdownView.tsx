"use client";

import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

/** A code block with a copy button, like the ones in Claude's artifacts. */
function CodeBlock(props: React.HTMLAttributes<HTMLPreElement>) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard?.writeText(ref.current?.innerText ?? "").then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }
  return (
    <div className="md-code">
      <button type="button" onClick={copy} className="md-copy" aria-label="คัดลอกโค้ด">
        <i className={`pi ${copied ? "pi-check" : "pi-copy"}`} aria-hidden /> {copied ? "คัดลอกแล้ว" : "คัดลอก"}
      </button>
      <pre ref={ref} {...props} />
    </div>
  );
}

/**
 * Renders GitHub-flavoured markdown: headings, tables, task lists, highlighted
 * code. Raw HTML in the file is not rendered, and unsafe link targets are dropped
 * by react-markdown, so an uploaded file can't run script in the reader's browser.
 */
export default function MarkdownView({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={{
          pre: CodeBlock,
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
