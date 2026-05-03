"use client";

import * as React from "react";
import { createContext, useContext, useState } from "react";

const OlIndexContext = createContext(0);
import { Check, CheckCheck, Copy, Sparkles } from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import type { ChatTurn } from "@/lib/types";

export function MessageTurn({ turn }: { turn: ChatTurn }) {
  if (turn.role === "summary") {
    return (
      <div className="border-l-2 border-border bg-surface-2/40 px-3 py-2 text-[11px] text-text-mute whitespace-pre-wrap">
        {turn.content}
      </div>
    );
  }
  if (turn.role === "system") {
    return (
      <div className="flex items-center justify-center gap-2 py-2 px-4">
        <svg
          className="h-3.5 w-3.5 shrink-0 text-text-mute"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <circle cx="8" cy="8" r="6.5" />
          <path d="M8 5.5v1M8 8.5v3" strokeLinecap="round" />
        </svg>
        <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-text-mute text-center">
          {turn.content}
        </span>
      </div>
    );
  }
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] space-y-1">
          <div
            className="rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-text whitespace-pre-wrap"
            style={{ background: "#FFF0EB", border: "1px solid #FFD8C8" }}
          >
            {turn.content}
          </div>
          {turn.at && (
            <div className="flex items-center justify-end gap-1 pr-1">
              <span className="text-[11px] text-text-mute">
                {new Date(turn.at).toLocaleTimeString(undefined, {
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
              <CheckCheck className="h-3 w-3 text-text-mute" strokeWidth={2} />
            </div>
          )}
        </div>
      </div>
    );
  }
  // assistant
  return <AssistantBubble content={turn.content ?? ""} at={turn.at} />;
}

function AssistantBubble({ content, at }: { content: string; at?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      toast.error("Could not copy");
    }
  };

  return (
    <div className="flex justify-start gap-3 group">
      {/* Spark avatar */}
      <div
        className="shrink-0 h-7 w-7 rounded-lg flex items-center justify-center mt-0.5"
        style={{ background: "var(--accent)" }}
        aria-hidden
      >
        <Sparkles className="h-3.5 w-3.5 text-white" strokeWidth={1.8} />
      </div>

      <div className="max-w-[80%] space-y-1">
        <div className="relative bg-surface border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text">
          <button
            type="button"
            onClick={handleCopy}
            title="Copy"
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 text-text-mute hover:text-text"
          >
            {copied ? (
              <Check className="h-3 w-3" strokeWidth={2} />
            ) : (
              <Copy className="h-3 w-3" strokeWidth={1.8} />
            )}
          </button>
          <ReactMarkdown
            components={{
              p: ({ children }) => (
                <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
              ),
              ol: ({ children }) => {
                const items = React.Children.toArray(children).filter(
                  React.isValidElement
                );
                return (
                  <ol className="mt-2 list-none p-0 space-y-2">
                    {items.map((item, idx) => (
                      <OlIndexContext.Provider key={idx} value={idx + 1}>
                        {item}
                      </OlIndexContext.Provider>
                    ))}
                  </ol>
                );
              },
              li: ({ children }) => {
                const num = useContext(OlIndexContext);
                return (
                  <li className="flex items-start gap-2.5">
                    {num > 0 && (
                      <span
                        className="shrink-0 mt-0.5 h-5 w-5 rounded-full flex items-center justify-center text-white text-[10px] font-semibold leading-none"
                        style={{ background: "var(--accent)" }}
                      >
                        {num}
                      </span>
                    )}
                    <span className="flex-1">{children}</span>
                  </li>
                );
              },
              ul: ({ children }) => (
                <ul className="mt-2 space-y-1.5 list-disc pl-4">{children}</ul>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-text">{children}</strong>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
        {at && (
          <div className="pl-1 text-[11px] text-text-mute">
            {new Date(at).toLocaleTimeString(undefined, {
              hour: "numeric",
              minute: "2-digit",
            })}
          </div>
        )}
      </div>
    </div>
  );
}
