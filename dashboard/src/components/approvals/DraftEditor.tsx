"use client";

import { useEffect, useState } from "react";
import { Loader2, Save, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface DraftEditorProps {
  initialSubject: string;
  initialBody: string;
  onCancel: () => void;
  onSave: (subject: string, body: string) => Promise<void>;
}

export function DraftEditor({
  initialSubject,
  initialBody,
  onCancel,
  onSave,
}: DraftEditorProps) {
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSubject(initialSubject);
    setBody(initialBody);
  }, [initialSubject, initialBody]);

  const dirty = subject !== initialSubject || body !== initialBody;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(subject, body);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-mute">
          Subject
        </Label>
        <Input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="font-mono text-sm"
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-mute">
          Body
        </Label>
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={10}
          className="font-mono text-sm leading-relaxed resize-y"
        />
      </div>
      <div className="flex items-center justify-between pt-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
          {dirty ? "unsaved changes" : "no changes"}
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={saving}>
            <X className="h-3.5 w-3.5" /> Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!dirty || saving}>
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…
              </>
            ) : (
              <>
                <Save className="h-3.5 w-3.5" /> Save
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
