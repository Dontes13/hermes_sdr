"use client";

import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api";
import type { ConfigKey } from "@/lib/types";

interface FieldDef {
  key: ConfigKey;
  label: string;
  description?: string;
  placeholder?: string;
  type?: "text" | "number" | "url";
  min?: number;
  max?: number;
  validate?: (value: string) => string | null;
}

const FIELDS: FieldDef[] = [
  {
    key: "sender_name",
    label: "Sender name",
    description: "Appears on drafted emails and in reply signatures.",
    placeholder: "Enrique",
  },
  {
    key: "sender_title",
    label: "Sender title",
    description: "Shown in outgoing email signature line.",
    placeholder: "CTO, Helios Marketing",
  },
  {
    key: "target_cities",
    label: "Target cities",
    description: "Comma-separated, e.g. Miami, Tampa, Austin.",
    placeholder: "Miami, Tampa",
  },
  {
    key: "calendly_link",
    label: "Calendly link",
    description: "Used by the reply agent when a broker shows booking intent.",
    placeholder: "https://calendly.com/...",
    type: "url",
    validate: (v) => {
      if (!v) return null;
      try {
        const url = new URL(v);
        if (url.protocol !== "http:" && url.protocol !== "https:") {
          return "Must be a http(s) URL";
        }
        return null;
      } catch {
        return "Invalid URL";
      }
    },
  },
  {
    key: "daily_lead_cap",
    label: "Daily lead cap",
    description: "Upper bound on leads processed per daily run.",
    type: "number",
    min: 1,
    max: 100,
    placeholder: "15",
    validate: (v) => {
      const n = Number(v);
      if (!Number.isFinite(n)) return "Must be a number";
      if (n < 1 || n > 100) return "Must be between 1 and 100";
      if (!Number.isInteger(n)) return "Must be an integer";
      return null;
    },
  },
];

interface ConfigEditorProps {
  config: Partial<Record<ConfigKey, string>>;
  onSaved?: () => void;
  /** If provided, only render these keys. Otherwise renders all. */
  keys?: ConfigKey[];
  title?: string;
  description?: string;
}

export function ConfigEditor({
  config,
  onSaved,
  keys,
  title = "Configuration",
  description,
}: ConfigEditorProps) {
  const visible = keys
    ? FIELDS.filter((f) => keys.includes(f.key))
    : FIELDS;
  return (
    <div className="border border-border bg-surface">
      <div className="border-b border-border px-4 py-2.5">
        <div className="label-sm">{title}</div>
        {description && (
          <div className="text-[11px] text-text-mute pt-1 leading-relaxed">
            {description}
          </div>
        )}
      </div>
      <div className="divide-y divide-border">
        {visible.map((field) => (
          <ConfigField
            key={field.key}
            field={field}
            initialValue={config[field.key] ?? ""}
            onSaved={onSaved}
          />
        ))}
      </div>
    </div>
  );
}

function ConfigField({
  field,
  initialValue,
  onSaved,
}: {
  field: FieldDef;
  initialValue: string;
  onSaved?: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  const dirty = value !== initialValue;
  const validationError = field.validate?.(value) ?? null;

  const handleSave = async () => {
    if (validationError) {
      toast.error(validationError);
      return;
    }
    setSaving(true);
    try {
      await api.setConfig(field.key, value);
      toast.success(`${field.label} saved`);
      onSaved?.();
    } catch (e) {
      toast.error(`Save failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-[200px_1fr_auto] gap-4 items-start px-5 py-4">
      <div className="space-y-1 pt-1">
        <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
          {field.label}
        </Label>
        {field.description && (
          <div className="text-[11px] text-text-mute leading-relaxed">
            {field.description}
          </div>
        )}
      </div>
      <div className="space-y-1">
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={field.placeholder}
          type={field.type === "number" ? "number" : "text"}
          min={field.min}
          max={field.max}
          className="font-mono text-sm"
        />
        {validationError && (
          <div className="text-[11px]" style={{ color: "var(--danger)" }}>
            {validationError}
          </div>
        )}
      </div>
      <Button
        size="sm"
        onClick={handleSave}
        disabled={!dirty || saving || Boolean(validationError)}
      >
        {saving ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Saving…
          </>
        ) : (
          <>
            <Save className="h-3.5 w-3.5" />
            Save
          </>
        )}
      </Button>
    </div>
  );
}
