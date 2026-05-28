"use client";

import { useEffect, useState } from "react";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { useVariants } from "@/lib/hooks/useVariants";
import type { SubjectVariant } from "@/lib/types";

export function VariantsEditor() {
  const { data: variants, mutate } = useVariants();
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="border border-border bg-surface">
      <div className="border-b border-border px-4 py-2.5">
        <div className="label-sm">Subject line variants</div>
        <div className="text-[11px] text-text-mute pt-1 leading-relaxed">
          Each active variant is assigned randomly at draft time (50/50). Only the subject
          line prompt varies — body generation is identical for all variants.
        </div>
      </div>

      <div className="divide-y divide-border">
        {(variants ?? []).map((v) => (
          <VariantRow key={v.id} variant={v} onMutate={mutate} />
        ))}
      </div>

      {showNew && (
        <div className="border-t border-border">
          <NewVariantRow
            onCreated={() => {
              setShowNew(false);
              mutate();
            }}
            onCancel={() => setShowNew(false)}
          />
        </div>
      )}

      {!showNew && (
        <div className="px-4 py-3 border-t border-border">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowNew(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            New variant
          </Button>
        </div>
      )}
    </div>
  );
}

function VariantRow({
  variant,
  onMutate,
}: {
  variant: SubjectVariant;
  onMutate: () => void;
}) {
  const [name, setName] = useState(variant.name);
  const [prompt, setPrompt] = useState(variant.subject_prompt);
  const [isActive, setIsActive] = useState(variant.is_active);
  const [saving, setSaving] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    setName(variant.name);
    setPrompt(variant.subject_prompt);
    setIsActive(variant.is_active);
  }, [variant]);

  const dirty =
    name !== variant.name ||
    prompt !== variant.subject_prompt ||
    isActive !== variant.is_active;

  const handlePreview = async () => {
    setPreviewing(true);
    setPreviewError(null);
    try {
      const result = await api.previewVariant(variant.id);
      setPreviewResult(result.preview);
    } catch (e) {
      setPreviewError(errorMessage(e));
      setPreviewResult(null);
    } finally {
      setPreviewing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateVariant(variant.id, {
        name: name.trim(),
        subject_prompt: prompt.trim(),
        is_active: isActive,
      });
      toast.success(`"${name.trim()}" saved`);
      onMutate();
    } catch (e) {
      toast.error(`Save failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.deleteVariant(variant.id);
      toast.success(`"${variant.name}" deleted`);
      setShowDeleteDialog(false);
      onMutate();
    } catch (e) {
      toast.error(`Delete failed: ${errorMessage(e)}`);
      setDeleting(false);
    }
  };

  return (
    <>
    <div className="px-5 py-4 space-y-3">
      <div className="grid grid-cols-[200px_1fr_auto_auto_auto] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            Name
          </Label>
          <div className="text-[11px] text-text-mute leading-relaxed">
            Short label for this variant (e.g. &ldquo;Variant A — Direct&rdquo;).
          </div>
        </div>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Variant A — Direct"
          className="font-mono text-sm"
        />
        <Button
          size="sm"
          variant="outline"
          onClick={handlePreview}
          disabled={previewing}
        >
          {previewing ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Preview…
            </>
          ) : (
            "Preview"
          )}
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!dirty || saving || !name.trim() || !prompt.trim()}
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
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowDeleteDialog(true)}
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete
        </Button>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            Subject prompt
          </Label>
          <div className="text-[11px] text-text-mute leading-relaxed">
            Instruction passed to the model for subject line style. Technical rules
            (lowercase, under 8 words, no emojis) always apply.
          </div>
        </div>
        <div className="space-y-2">
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={6}
            className="font-mono text-sm resize-y"
            placeholder="Generate a short, direct subject line…"
          />
          {previewResult && (
            <div className="rounded border border-border p-2 text-sm font-mono">
              {previewResult}
            </div>
          )}
          {previewError && (
            <div className="rounded border border-red-500/40 p-2 text-sm font-mono text-red-500">
              {previewError}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4 items-center">
        <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
          Active
        </Label>
        <label className="flex items-center gap-2 cursor-pointer w-fit">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-3.5 w-3.5 accent-primary cursor-pointer"
          />
          <span className="text-[11px] text-text-mute">
            {isActive ? "Included in random assignment" : "Excluded from random assignment"}
          </span>
        </label>
      </div>
    </div>

    <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Delete variant?</DialogTitle>
          <DialogDescription>
            This will delete the variant. Past sends using it stay in the database. Continue?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={deleting}>Cancel</Button>
          </DialogClose>
          <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}

function NewVariantRow({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    setSaving(true);
    try {
      await api.createVariant({
        name: name.trim(),
        subject_prompt: prompt.trim(),
        is_active: isActive,
      });
      toast.success(`"${name.trim()}" created`);
      onCreated();
    } catch (e) {
      toast.error(`Create failed: ${errorMessage(e)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="px-5 py-4 space-y-3 bg-surface/50">
      <div className="grid grid-cols-[200px_1fr_auto_auto] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            Name
          </Label>
          <div className="text-[11px] text-text-mute leading-relaxed">
            Short label for this variant.
          </div>
        </div>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Variant C — Question"
          className="font-mono text-sm"
          autoFocus
        />
        <Button
          size="sm"
          onClick={handleCreate}
          disabled={saving || !name.trim() || !prompt.trim()}
        >
          {saving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Creating…
            </>
          ) : (
            <>
              <Plus className="h-3.5 w-3.5" />
              Create
            </>
          )}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
        <div className="space-y-1 pt-1">
          <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
            Subject prompt
          </Label>
          <div className="text-[11px] text-text-mute leading-relaxed">
            Style instruction for subject line generation.
          </div>
        </div>
        <Textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={5}
          className="font-mono text-sm resize-y"
          placeholder="Generate a short, direct subject line (under 8 words)…"
        />
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4 items-center">
        <Label className="font-mono text-[11px] uppercase tracking-wider text-text-dim">
          Active
        </Label>
        <label className="flex items-center gap-2 cursor-pointer w-fit">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-3.5 w-3.5 accent-primary cursor-pointer"
          />
          <span className="text-[11px] text-text-mute">
            Include in random assignment immediately
          </span>
        </label>
      </div>
    </div>
  );
}
