"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Server } from "lucide-react";

export function ToolChip({
  name,
  result,
}: {
  name: string;
  result?: unknown;
}) {
  const [open, setOpen] = useState(false);
  const hasResult = result !== undefined && result !== null;

  return (
    <div className="flex justify-start">
      <div>
        <button
          type="button"
          onClick={() => hasResult && setOpen((v) => !v)}
          disabled={!hasResult}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-surface text-[11px] font-medium tracking-[0.04em] text-text-dim transition-colors hover:bg-surface-2 hover:border-border-strong disabled:cursor-default"
        >
          <Server className="h-3 w-3 text-text-mute" strokeWidth={1.6} />
          <span>
            CALLED{" "}
            <span className="text-text font-semibold">{name.toUpperCase()}</span>
          </span>
          {hasResult ? (
            open ? (
              <ChevronDown className="h-3 w-3" strokeWidth={1.8} />
            ) : (
              <ChevronRight className="h-3 w-3" strokeWidth={1.8} />
            )
          ) : null}
        </button>
        {open && hasResult && (
          <pre className="mt-2 p-3 bg-surface-2 border border-border rounded-xl font-mono text-[11px] text-text-dim whitespace-pre-wrap max-h-64 overflow-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
