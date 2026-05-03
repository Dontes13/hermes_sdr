"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { PendingAction } from "@/lib/types";

type FieldKind = "textarea" | "number" | "select" | "text";
interface FieldHint {
  kind: FieldKind;
  options?: string[];
  nullable?: boolean;
  placeholder?: string;
  suffix?: string;
}

// Per-tool field hints. Centralized so the card stays declarative.
const FIELD_HINTS: Record<string, Record<string, FieldHint>> = {
  create_campaign: {
    name: { kind: "text", placeholder: "Q2 Miami Coffee Shops" },
    city: { kind: "text" },
    target: {
      kind: "text",
      placeholder: "e.g. boutique coffee shops",
    },
    sample_email: {
      kind: "textarea",
      nullable: true,
      placeholder: "Optional tone reference",
    },
    autonomy: { kind: "select", options: ["full", "review_drafts"] },
    daily_send_cap: { kind: "number", suffix: "/day" },
    total_lead_cap: {
      kind: "number",
      nullable: true,
      placeholder: "unlimited",
      suffix: "leads",
    },
  },
  update_campaign_status: {
    campaign_id: { kind: "text" },
    status: {
      kind: "select",
      options: ["active", "paused", "archived"],
    },
  },
};

function hintFor(tool: string, key: string, v: unknown): FieldHint {
  const fromMap = FIELD_HINTS[tool]?.[key];
  if (fromMap) return fromMap;
  if (typeof v === "number") return { kind: "number" };
  if (typeof v === "string" && v.length > 60)
    return { kind: "textarea", nullable: v === null };
  return { kind: "text", nullable: v === null };
}

export function PendingActionCard({
  action,
  confirming,
  onConfirm,
  onCancel,
}: {
  action: PendingAction;
  confirming: boolean;
  onConfirm: (edits?: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [edits, setEdits] = useState<Record<string, unknown>>(action.tool_args);

  useEffect(() => {
    setEdits(action.tool_args);
  }, [action.action_id, action.tool_args]);

  const dirty = JSON.stringify(edits) !== JSON.stringify(action.tool_args);

  return (
    <div
      className="border bg-surface shadow-md"
      style={{
        borderColor: "var(--accent)",
        boxShadow:
          "var(--shadow-md), 0 0 0 1px color-mix(in oklch, var(--accent) 30%, transparent)",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="label-xs"
            style={{ color: "var(--accent)" }}
          >
            Pending action
          </span>
          <span className="text-sm font-semibold text-text truncate">
            {action.tool_name}
          </span>
          {dirty && (
            <span
              className="label-xs px-1.5 py-0.5 border"
              style={{
                color: "var(--warn)",
                borderColor: "var(--warn)",
              }}
            >
              edited
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onCancel}
          disabled={confirming}
          className="text-text-mute hover:text-text transition-colors"
          title="Cancel"
        >
          <X className="h-4 w-4" strokeWidth={1.8} />
        </button>
      </div>

      {/* Body — two-column key/value grid */}
      <div className="divide-y divide-border">
        {Object.entries(action.tool_args).map(([k, v]) => {
          const hint = hintFor(action.tool_name, k, v);
          return (
            <EditableRow
              key={k}
              name={k}
              value={edits[k]}
              original={v}
              hint={hint}
              disabled={confirming}
              onChange={(next) =>
                setEdits((prev) => ({ ...prev, [k]: next }))
              }
            />
          );
        })}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-3">
        <div className="label-xs">
          {dirty
            ? "Edits will be validated before the action runs."
            : "Fields are editable before confirming."}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={onCancel}
            disabled={confirming}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => onConfirm(dirty ? edits : undefined)}
            disabled={confirming}
            className="gap-1.5"
          >
            {confirming ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" strokeWidth={1.8} />
            )}
            Confirm
          </Button>
        </div>
      </div>
    </div>
  );
}

function EditableRow({
  name,
  value,
  original,
  hint,
  disabled,
  onChange,
}: {
  name: string;
  value: unknown;
  original: unknown;
  hint: FieldHint;
  disabled: boolean;
  onChange: (next: unknown) => void;
}) {
  const changed = JSON.stringify(value) !== JSON.stringify(original);

  let input: React.ReactNode;
  if (hint.kind === "number") {
    const displayed =
      value === null || value === undefined ? "" : String(value);
    input = (
      <div className="relative">
        <Input
          type="number"
          value={displayed}
          placeholder={hint.placeholder ?? (hint.nullable ? "null" : "")}
          disabled={disabled}
          className="font-mono text-sm pr-14"
          onChange={(e) => {
            const v = e.target.value;
            if (v === "") {
              onChange(hint.nullable ? null : 0);
            } else {
              const n = Number(v);
              onChange(Number.isFinite(n) ? n : v);
            }
          }}
        />
        {hint.suffix && (
          <span className="absolute inset-y-0 right-3 flex items-center label-xs pointer-events-none">
            {hint.suffix}
          </span>
        )}
      </div>
    );
  } else if (hint.kind === "select" && hint.options) {
    input = (
      <Select
        value={typeof value === "string" ? value : ""}
        onValueChange={(v) => onChange(v)}
        disabled={disabled}
      >
        <SelectTrigger className="w-full font-mono text-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {hint.options.map((opt) => (
            <SelectItem key={opt} value={opt} className="font-mono text-sm">
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  } else if (hint.kind === "textarea") {
    const displayed =
      value === null || value === undefined ? "" : String(value);
    input = (
      <Textarea
        value={displayed}
        placeholder={hint.placeholder ?? (hint.nullable ? "null" : "")}
        disabled={disabled}
        rows={Math.min(10, Math.max(3, displayed.split("\n").length))}
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "" && hint.nullable ? null : v);
        }}
        className="font-mono text-sm max-h-60"
      />
    );
  } else {
    const displayed =
      value === null || value === undefined ? "" : String(value);
    input = (
      <Input
        value={displayed}
        placeholder={hint.placeholder ?? (hint.nullable ? "null" : "")}
        disabled={disabled}
        className="font-mono text-sm"
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "" && hint.nullable ? null : v);
        }}
      />
    );
  }

  return (
    <div className="grid grid-cols-[160px_1fr] gap-4 px-4 py-2.5 items-start">
      <div className="flex items-center gap-1.5 justify-end pt-2">
        <span className="label-md">{name}</span>
        {changed && (
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: "var(--warn)" }}
            aria-label="modified"
          />
        )}
      </div>
      <div>{input}</div>
    </div>
  );
}
