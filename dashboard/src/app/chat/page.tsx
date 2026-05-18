"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import {
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Braces,
  LayoutGrid,
} from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import { MessageTurn } from "@/components/chat/MessageTurn";
import { ToolChip } from "@/components/chat/ToolChip";
import { PendingActionCard } from "@/components/chat/PendingActionCard";
import { api, errorMessage } from "@/lib/api";
import type {
  ChatSessionSummary,
  ChatTurn,
  PendingAction,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const SESSION_KEY = "helios_chat_session";

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: sessions, mutate: refreshSessions } = useSWR<
    ChatSessionSummary[]
  >("chat_sessions", () => api.listChatSessions(), {
    refreshInterval: 30_000,
    keepPreviousData: true,
  });

  useEffect(() => {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) {
      api
        .getChatSession(existing)
        .then((s) => {
          setSessionId(s.id);
          setMessages(s.messages ?? []);
          setPending(s.pending_action);
        })
        .catch(() => {
          localStorage.removeItem(SESSION_KEY);
          bootstrap();
        });
    } else {
      bootstrap();
    }
    function bootstrap() {
      api
        .createChatSession()
        .then((s) => {
          localStorage.setItem(SESSION_KEY, s.id);
          setSessionId(s.id);
          setMessages([]);
          setPending(null);
          refreshSessions();
        })
        .catch((e) => toast.error(`Chat init failed: ${errorMessage(e)}`));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, pending]);

  const switchSession = useCallback(
    async (id: string) => {
      if (id === sessionId) return;
      setLoadingSession(true);
      try {
        const s = await api.getChatSession(id);
        localStorage.setItem(SESSION_KEY, s.id);
        setSessionId(s.id);
        setMessages(s.messages ?? []);
        setPending(s.pending_action);
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setLoadingSession(false);
      }
    },
    [sessionId]
  );

  const handleNewSession = useCallback(async () => {
    try {
      const s = await api.createChatSession();
      localStorage.setItem(SESSION_KEY, s.id);
      setSessionId(s.id);
      setMessages([]);
      setPending(null);
      refreshSessions();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [refreshSessions]);

  const handleDeleteSession = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!confirm("Delete this conversation?")) return;
      try {
        await api.deleteChatSession(id);
        refreshSessions();
        if (id === sessionId) {
          localStorage.removeItem(SESSION_KEY);
          handleNewSession();
        }
      } catch (err) {
        toast.error(errorMessage(err));
      }
    },
    [sessionId, refreshSessions, handleNewSession]
  );

  const handleSend = useCallback(async () => {
    if (!sessionId || !input.trim() || busy) return;
    const msg = input.trim();
    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: msg, at: new Date().toISOString() },
    ]);
    try {
      const res = await api.sendChatMessage(sessionId, msg);
      setMessages(res.messages);
      setPending(res.pending_action);
      refreshSessions();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [sessionId, input, busy, refreshSessions]);

  const handleConfirm = useCallback(
    async (editedArgs?: Record<string, unknown>) => {
      if (!sessionId || !pending) return;
      setConfirming(true);
      try {
        const res = await api.confirmChatAction(
          sessionId,
          pending.action_id,
          editedArgs
        );
        setMessages(res.messages);
        setPending(null);
        toast.success("Action confirmed");
        refreshSessions();
      } catch (e) {
        toast.error(errorMessage(e));
      } finally {
        setConfirming(false);
      }
    },
    [sessionId, pending, refreshSessions]
  );

  const handleCancel = useCallback(async () => {
    if (!sessionId) return;
    setConfirming(true);
    try {
      await api.cancelChatAction(sessionId);
      const s = await api.getChatSession(sessionId);
      setMessages(s.messages);
      setPending(null);
      refreshSessions();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setConfirming(false);
    }
  }, [sessionId, refreshSessions]);

  return (
    <div className="flex h-screen">
      <SessionsSidebar
        sessions={sessions}
        activeId={sessionId}
        onSelect={switchSession}
        onNew={handleNewSession}
        onDelete={handleDeleteSession}
      />

      <div className="flex-1 flex flex-col min-w-0 bg-bg">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-4">
          <div className="flex items-center gap-3">
            <div
              className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "var(--accent)" }}
              aria-hidden
            >
              <Sparkles className="h-4 w-4 text-white" strokeWidth={1.8} />
            </div>
            <div>
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.06em]"
                style={{ color: "var(--accent)" }}
              >
                AI Assistant
              </div>
              <div className="text-[13px] text-text-dim leading-snug">
                Ask questions. Propose campaigns. Confirm write actions.
              </div>
            </div>
          </div>
          <button
            type="button"
            className="p-1.5 rounded-lg text-text-mute hover:text-text hover:bg-surface-2 transition-colors"
          >
            <MoreHorizontal className="h-4 w-4" strokeWidth={1.8} />
          </button>
        </header>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-8 py-6 space-y-5"
        >
          {loadingSession ? (
            <div className="flex items-center gap-2 text-[12px] text-text-mute">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading session…
            </div>
          ) : messages.length === 0 ? (
            <EmptyChatHints />
          ) : (
            messages.map((m, i) => {
              if (m.role === "tool") {
                return <ToolChip key={i} name={m.name ?? "?"} result={m.result} />;
              }
              return <MessageTurn key={i} turn={m} />;
            })
          )}

          {pending && (
            <PendingActionCard
              action={pending}
              confirming={confirming}
              onConfirm={handleConfirm}
              onCancel={handleCancel}
            />
          )}

          {busy && (
            <div className="flex items-center gap-2 text-[12px] text-text-mute">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Thinking…
            </div>
          )}
        </div>

        {/* Input area */}
        <footer className="border-t border-border bg-surface px-6 pt-4 pb-5">
          <div className="border border-border rounded-xl bg-surface overflow-hidden">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask something, or propose a campaign…"
              rows={2}
              disabled={busy || !sessionId}
              className="border-0 resize-none shadow-none focus-visible:ring-0 bg-transparent text-sm text-text placeholder:text-text-mute px-4 pt-3 pb-2"
            />
            <div className="flex items-center justify-between px-3 pb-3">
              <div className="flex items-center gap-1">
                <ToolbarButton title="Suggest">
                  <Sparkles className="h-3.5 w-3.5" strokeWidth={1.6} />
                </ToolbarButton>
                <ToolbarButton title="Attach">
                  <Paperclip className="h-3.5 w-3.5" strokeWidth={1.6} />
                </ToolbarButton>
                <ToolbarButton title="Code">
                  <Braces className="h-3.5 w-3.5" strokeWidth={1.6} />
                </ToolbarButton>
                <ToolbarButton title="Table">
                  <LayoutGrid className="h-3.5 w-3.5" strokeWidth={1.6} />
                </ToolbarButton>
              </div>
              <button
                type="button"
                onClick={handleSend}
                disabled={busy || !input.trim() || !sessionId}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[13px] font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ background: "var(--accent)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--accent-hover)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--accent)")
                }
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" strokeWidth={1.8} />
                )}
                Send
              </button>
            </div>
          </div>
          <div className="pt-2 text-[11px] text-text-mute">
            Enter to send · Shift + Enter for new line
          </div>
        </footer>
      </div>
    </div>
  );
}

function ToolbarButton({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <button
      type="button"
      title={title}
      className="p-1.5 rounded-lg text-text-mute hover:text-text hover:bg-surface-2 transition-colors"
    >
      {children}
    </button>
  );
}

function EmptyChatHints() {
  return (
    <div className="border border-border rounded-xl bg-surface p-6 space-y-3">
      <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-mute">
        Try asking
      </div>
      <ul className="text-sm text-text-dim space-y-2">
        <li>&quot;What&apos;s our response rate so far?&quot;</li>
        <li>&quot;List active campaigns&quot;</li>
        <li>
          &quot;Start a campaign targeting boutique coffee shops in Austin&quot;
        </li>
      </ul>
    </div>
  );
}

function SessionsSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: ChatSessionSummary[] | undefined;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
}) {
  return (
    <aside className="w-64 shrink-0 border-r border-border bg-surface flex flex-col">
      {/* New chat button */}
      <div className="px-4 pt-4 pb-3">
        <button
          type="button"
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-medium text-white transition-colors"
          style={{ background: "var(--accent)" }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "var(--accent-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "var(--accent)")
          }
        >
          <Plus className="h-4 w-4" strokeWidth={2} />
          New chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 pb-2">
          <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-text-mute">
            Recent conversations
          </span>
        </div>

        {sessions === undefined ? (
          <div className="px-4 py-2 text-[12px] text-text-mute">Loading…</div>
        ) : sessions.length === 0 ? (
          <div className="px-4 py-2 text-[12px] text-text-mute">
            No conversations yet
          </div>
        ) : (
          <div className="px-2 space-y-0.5">
            {sessions.map((s) => {
              const active = s.id === activeId;
              return (
                <div
                  key={s.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(s.id);
                    }
                  }}
                  className={cn(
                    "group px-3 py-2.5 rounded-xl cursor-pointer outline-none flex items-start gap-2.5 transition-colors",
                    active
                      ? "bg-surface-2"
                      : "hover:bg-surface-2/60"
                  )}
                >
                  <MessageSquare
                    className="h-3.5 w-3.5 mt-0.5 shrink-0 text-text-mute"
                    strokeWidth={1.6}
                  />
                  <div className="flex-1 min-w-0">
                    <div
                      className={cn(
                        "text-[13px] font-medium truncate",
                        active ? "text-text" : "text-text-dim"
                      )}
                    >
                      {s.preview || "New chat"}
                    </div>
                    <div className="flex items-center gap-1.5 pt-0.5">
                      <MessageSquare className="h-2.5 w-2.5 text-text-mute" strokeWidth={1.6} />
                      <span className="text-[11px] text-text-mute">{s.message_count}</span>
                      {s.has_pending && (
                        <span
                          className="h-1.5 w-1.5 rounded-full shrink-0"
                          style={{ background: "var(--accent)" }}
                          aria-label="pending action"
                        />
                      )}
                      <span className="text-[11px] text-text-mute ml-auto">
                        {relTime(s.updated_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => onDelete(s.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-text-mute hover:text-[color:var(--danger)] transition-opacity mt-0.5"
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" strokeWidth={1.8} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* View all link */}
      <div className="border-t border-border px-4 py-3">
        <button
          type="button"
          className="w-full flex items-center justify-between text-[12px] text-text-mute hover:text-text transition-colors"
        >
          <span>View all conversations</span>
          <LayoutGrid className="h-3.5 w-3.5" strokeWidth={1.6} />
        </button>
      </div>
    </aside>
  );
}

function relTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(iso).toLocaleDateString();
}
