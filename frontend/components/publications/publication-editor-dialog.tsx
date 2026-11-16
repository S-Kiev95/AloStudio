"use client";

import {
  ArrowDown,
  ArrowUp,
  Bookmark,
  Check,
  Eye,
  FileSignature,
  Film,
  FolderOpen,
  Images,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  describeScheduledFor,
  fromDatetimeLocalInput,
  toDatetimeLocalInput,
} from "@/components/agenda/week-utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Textarea } from "@/components/ui/textarea";
import {
  type MediaAsset,
  type MediaKind,
  useInfiniteMediaAssets,
  useUploadMedia,
  validateMediaFile,
} from "@/lib/api/media";
import {
  type Channel,
  type InstagramPostType,
  type MediaIn,
  type ParsedPublicationError,
  parsePublicationError,
  type Publication,
  type PublicationSet,
  type TargetIn,
  type TikTokSettings,
  useCreatePublication,
  useCreatePublicationSet,
  usePublicationSets,
  usePublicationSignatures,
  useUpdatePublication,
  useUpdatePublicationSet,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

import { ChannelAvatar, channelDisplayName, NetworkIcon } from "./network-icon";
import {
  channelCharLimit,
  minSharedCharLimit,
  type TargetRuleInput,
  textLength,
  validatePublicationTargets,
  xChannelsWithLink,
} from "./network-rules";
import { PublicationErrorAlert } from "./publication-error-alert";
import {
  EMPTY_TIKTOK_SETTINGS,
  normalizeTikTokSettings,
  TikTokConsent,
  TikTokTargetSettings,
} from "./tiktok-target-settings";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

type SelectedMediaItem = {
  media_id?: number;
  type: "image" | "video";
  url: string;
  filename?: string | null;
};

type PerChannelConfig = {
  postType: InstagramPostType;
  tiktok: TikTokSettings;
  customizeText: boolean;
  customText: string;
};

type WhenMode = "now" | "schedule";

const IG_POST_TYPES: { value: InstagramPostType; label: string }[] = [
  { value: "feed", label: "Feed" },
  { value: "reels", label: "Reels" },
  { value: "story", label: "Story" },
];

const MEDIA_PICKER_FILTERS: { value: MediaKind | undefined; label: MessageKey }[] =
  [
    { value: undefined, label: "publications.media.filters.all" },
    { value: "image", label: "publications.media.filters.images" },
    { value: "video", label: "publications.media.filters.videos" },
  ];

function normalizePostType(raw?: string): InstagramPostType {
  if (raw === "reels" || raw === "story") return raw;
  return "feed";
}

function serializeMedia(items: SelectedMediaItem[]): MediaIn[] {
  return items.map((m) =>
    m.media_id !== undefined
      ? { media_id: m.media_id }
      : { type: m.type, url: m.url },
  );
}

export function PublicationEditorDialog({
  accountId,
  open,
  onClose,
  channels,
  isAdmin,
  mode = "publication",
  initial,
  initialSet,
  defaultScheduledFor,
  onOpenDetail,
}: {
  accountId: string;
  open: boolean;
  onClose: () => void;
  channels: Channel[];
  isAdmin: boolean;
  mode?: "publication" | "set";
  initial?: Publication | null;
  initialSet?: PublicationSet | null;
  defaultScheduledFor?: Date | null;
  onOpenDetail?: (publication: Publication) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const isSetMode = mode === "set";
  const dialogRef = useRef<HTMLDialogElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const autoSigAppliedRef = useRef(false);

  const activeChannels = useMemo(
    () => channels.filter((c) => c.status === "active"),
    [channels],
  );

  const channelById = useMemo(
    () => new Map(channels.map((c) => [c.id, c])),
    [channels],
  );

  const [selectedChannelIds, setSelectedChannelIds] = useState<number[]>([]);
  const [channelConfigs, setChannelConfigs] = useState<
    Record<number, PerChannelConfig>
  >({});
  const [content, setContent] = useState("");
  const [selectedMedia, setSelectedMedia] = useState<SelectedMediaItem[]>([]);
  const [whenMode, setWhenMode] = useState<WhenMode>("now");
  const [scheduledFor, setScheduledFor] = useState("");
  const scheduledHint = describeScheduledFor(scheduledFor, undefined, locale);

  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryKind, setLibraryKind] = useState<MediaKind | undefined>(
    undefined,
  );
  const [signaturesOpen, setSignaturesOpen] = useState(false);
  const [setsOpen, setSetsOpen] = useState(false);
  const [savingSetOpen, setSavingSetOpen] = useState(false);
  const [setName, setSetName] = useState("");
  const [setFeedback, setSetFeedback] = useState<string | null>(null);

  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [apiError, setApiError] = useState<ParsedPublicationError | null>(null);

  const signaturesQuery = usePublicationSignatures(accountId, open);
  const setsQuery = usePublicationSets(accountId, open && !isSetMode);
  const libraryQuery = useInfiniteMediaAssets(accountId, {
    kind: libraryKind,
    enabled: open && libraryOpen,
  });

  const uploadMediaMutation = useUploadMedia(accountId);
  const createMutation = useCreatePublication(accountId);
  const updateMutation = useUpdatePublication(accountId);
  const createSetMutation = useCreatePublicationSet(accountId);
  const updateSetMutation = useUpdatePublicationSet(accountId);

  const isSubmitting =
    createMutation.isPending ||
    updateMutation.isPending ||
    createSetMutation.isPending ||
    updateSetMutation.isPending;

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) {
        if (typeof el.showModal === "function") {
          el.showModal();
        } else {
          el.setAttribute("open", "");
        }
      }
    } else if (el.open) {
      if (typeof el.close === "function") {
        el.close();
      } else {
        el.removeAttribute("open");
      }
    }
  }, [open]);

  // Reset form state whenever the dialog opens or switches target publication/set.
  useEffect(() => {
    if (!open) return;
    setSubmitAttempted(false);
    setApiError(null);
    setLibraryOpen(false);
    setSignaturesOpen(false);
    setSetsOpen(false);
    setSavingSetOpen(false);
    setSetFeedback(null);

    if (isSetMode) {
      autoSigAppliedRef.current = true;
      if (initialSet) {
        setSetName(initialSet.name);
        setContent(initialSet.content ?? "");
        setSelectedMedia(
          initialSet.media.map((m) => ({
            media_id: "media_id" in m ? m.media_id : undefined,
            type: m.type,
            url: m.url,
          })),
        );
        const validIds: number[] = [];
        const cfgs: Record<number, PerChannelConfig> = {};
        for (const t of initialSet.targets) {
          const ch = t.channel ?? channelById.get(t.channel_id);
          if (!ch || ch.status !== "active") continue;
          if (!validIds.includes(ch.id)) {
            validIds.push(ch.id);
          }
          cfgs[ch.id] = {
            postType: normalizePostType(t.settings?.post_type),
            tiktok: normalizeTikTokSettings(t.settings),
            customizeText: t.content_override !== null,
            customText: t.content_override ?? "",
          };
        }
        setSelectedChannelIds(validIds);
        setChannelConfigs(cfgs);
      } else {
        setSetName("");
        setSelectedChannelIds(
          activeChannels.length === 1 ? [activeChannels[0].id] : [],
        );
        setChannelConfigs({});
        setContent("");
        setSelectedMedia([]);
      }
      setWhenMode("now");
      setScheduledFor("");
      return;
    }

    setSetName("");
    if (initial) {
      autoSigAppliedRef.current = true;
      const validIds: number[] = [];
      const cfgs: Record<number, PerChannelConfig> = {};
      for (const t of initial.targets) {
        if (t.channel.status === "active") {
          validIds.push(t.channel.id);
        }
        cfgs[t.channel.id] = {
          postType: normalizePostType(t.settings?.post_type),
          tiktok: normalizeTikTokSettings(t.settings),
          customizeText: t.content_override !== null,
          customText: t.content_override ?? "",
        };
      }
      setSelectedChannelIds(validIds);
      setChannelConfigs(cfgs);
      setContent(initial.content ?? "");
      setSelectedMedia(
        initial.media.map((m) => ({
          media_id: m.media_id,
          type: m.type,
          url: m.url,
        })),
      );
      if (initial.scheduled_for) {
        setWhenMode("schedule");
        setScheduledFor(toDatetimeLocalInput(initial.scheduled_for));
      } else {
        setWhenMode("now");
        setScheduledFor("");
      }
    } else {
      autoSigAppliedRef.current = false;
      setSelectedChannelIds(
        activeChannels.length === 1 ? [activeChannels[0].id] : [],
      );
      setChannelConfigs({});
      setContent("");
      setSelectedMedia([]);
      if (defaultScheduledFor) {
        setWhenMode("schedule");
        setScheduledFor(toDatetimeLocalInput(defaultScheduledFor));
      } else {
        setWhenMode("now");
        const nextHour = new Date();
        nextHour.setMinutes(0, 0, 0);
        nextHour.setHours(nextHour.getHours() + 1);
        setScheduledFor(toDatetimeLocalInput(nextHour));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isSetMode, initial, initialSet, defaultScheduledFor]);

  // Auto-add signature when opening a NEW publication.
  useEffect(() => {
    if (!open || isSetMode || initial || autoSigAppliedRef.current) return;
    if (!signaturesQuery.data) return;
    autoSigAppliedRef.current = true;
    const autoSig = signaturesQuery.data.find((s) => s.auto_add);
    if (autoSig) {
      setContent((prev) => (prev === "" ? `\n\n${autoSig.content}` : prev));
    }
  }, [open, isSetMode, initial, signaturesQuery.data]);

  const selectedChannels = useMemo(
    () =>
      selectedChannelIds
        .map((id) => channelById.get(id))
        .filter((c): c is Channel => Boolean(c && c.status === "active")),
    [selectedChannelIds, channelById],
  );

  function configFor(channelId: number): PerChannelConfig {
    return (
      channelConfigs[channelId] ?? {
        postType: "feed",
        tiktok: EMPTY_TIKTOK_SETTINGS,
        customizeText: false,
        customText: "",
      }
    );
  }

  function updateConfig(
    channelId: number,
    patch: Partial<PerChannelConfig>,
  ) {
    setChannelConfigs((prev) => ({
      ...prev,
      [channelId]: { ...configFor(channelId), ...patch },
    }));
  }

  function toggleChannel(channelId: number) {
    setSelectedChannelIds((prev) =>
      prev.includes(channelId)
        ? prev.filter((id) => id !== channelId)
        : [...prev, channelId],
    );
  }

  function applySet(pubSet: PublicationSet) {
    autoSigAppliedRef.current = true;
    setContent(pubSet.content ?? "");
    setSelectedMedia(
      pubSet.media.map((m) => ({
        media_id: "media_id" in m ? m.media_id : undefined,
        type: m.type,
        url: m.url,
      })),
    );
    const nextIds: number[] = [];
    const nextConfigs: Record<number, PerChannelConfig> = {};
    for (const t of pubSet.targets) {
      const ch = t.channel ?? channelById.get(t.channel_id);
      if (!ch || ch.status !== "active") continue;
      if (!nextIds.includes(ch.id)) {
        nextIds.push(ch.id);
      }
      nextConfigs[ch.id] = {
        postType: normalizePostType(t.settings?.post_type),
        tiktok: normalizeTikTokSettings(t.settings),
        customizeText: t.content_override !== null,
        customText: t.content_override ?? "",
      };
    }
    setSelectedChannelIds(nextIds);
    setChannelConfigs(nextConfigs);
    setSetsOpen(false);
    setSetFeedback(t("publications.editor.setApplied", { name: pubSet.name }));
  }

  function appendSignature(sigContent: string) {
    autoSigAppliedRef.current = true;
    setContent((prev) => (prev ? `${prev}\n${sigContent}` : sigContent));
    setSignaturesOpen(false);
  }

  function toggleLibraryAsset(asset: MediaAsset) {
    setSelectedMedia((prev) => {
      const exists = prev.some((m) => m.media_id === asset.id);
      if (exists) {
        return prev.filter((m) => m.media_id !== asset.id);
      }
      return [
        ...prev,
        {
          media_id: asset.id,
          type: asset.kind,
          url: asset.url,
          filename: asset.filename,
        },
      ];
    });
  }

  function moveMedia(index: number, delta: -1 | 1) {
    setSelectedMedia((prev) => {
      const targetIndex = index + delta;
      if (targetIndex < 0 || targetIndex >= prev.length) return prev;
      const copy = [...prev];
      const [item] = copy.splice(index, 1);
      copy.splice(targetIndex, 0, item);
      return copy;
    });
  }

  function removeMedia(index: number) {
    setSelectedMedia((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUploadFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    setApiError(null);

    for (const file of files) {
      const msg = validateMediaFile(file);
      if (msg) {
        setApiError({ message: msg, errors: [] });
        return;
      }
    }

    try {
      for (const file of files) {
        const uploaded = await uploadMediaMutation.mutateAsync(file);
        setSelectedMedia((prev) => [
          ...prev,
          {
            media_id: uploaded.id,
            type: uploaded.kind,
            url: uploaded.url,
            filename: uploaded.filename,
          },
        ]);
      }
    } catch (err) {
      setApiError(parsePublicationError(err, t("publications.media.uploadFailed")));
    }
  }

  const ruleTargets: TargetRuleInput[] = useMemo(
    () =>
      selectedChannels.map((ch) => {
        const cfg = channelConfigs[ch.id];
        return {
          channel: ch,
          postType: cfg?.postType ?? "feed",
          tiktok: cfg?.tiktok ?? EMPTY_TIKTOK_SETTINGS,
          customContent: cfg?.customizeText ? cfg.customText : null,
        };
      }),
    [selectedChannels, channelConfigs],
  );

  const sharedLimit = useMemo(
    () => minSharedCharLimit(ruleTargets, selectedMedia),
    [ruleTargets, selectedMedia],
  );
  const sharedLength = sharedLimit
    ? textLength(sharedLimit.network, content)
    : Array.from(content).length;

  // The actions sit at the bottom of a scrolling dialog and the error at
  // the top: bring it into view, or a rejected save looks like a dead click.
  useEffect(() => {
    if (apiError) errorRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [apiError]);

  // Problems only a network's own panel can tell (a TikTok video longer
  // than the account allows), by channel.
  const [panelProblems, setPanelProblems] = useState<Record<number, string>>(
    {},
  );
  function reportPanelProblem(channelId: number, problem: string | null) {
    setPanelProblems((prev) => {
      if ((prev[channelId] ?? null) === problem) return prev;
      const next = { ...prev };
      if (problem) next[channelId] = problem;
      else delete next[channelId];
      return next;
    });
  }

  const ruleProblems = useMemo(
    () => [
      ...validatePublicationTargets(content, selectedMedia, ruleTargets, t),
      ...selectedChannels.flatMap((ch) =>
        panelProblems[ch.id] ? [panelProblems[ch.id]] : [],
      ),
    ],
    [content, selectedMedia, ruleTargets, selectedChannels, panelProblems, t],
  );

  const xLinkChannels = xChannelsWithLink(content, ruleTargets);

  // TikTok asks for the publish button itself to be disabled, with the
  // reason on hover, while a commercial disclosure has no option chosen.
  const disclosureBlock = selectedChannels.some((ch) => {
    const t = channelConfigs[ch.id]?.tiktok;
    return (
      ch.network === "tiktok" &&
      Boolean(t?.disclose && !t.brand_organic && !t.brand_content)
    );
  })
    ? t("publications.editor.tiktokDisclosure")
    : null;

  function buildTargetsPayload(): TargetIn[] {
    const initialOverrideIds = new Set(
      (initial?.targets ?? [])
        .filter((t) => t.content_override !== null)
        .map((t) => t.channel.id),
    );

    return selectedChannels.map((ch) => {
      const cfg = configFor(ch.id);
      const target: TargetIn = { channel_id: ch.id };
      if (ch.network === "instagram") {
        target.settings = { post_type: cfg.postType };
      } else if (ch.network === "tiktok") {
        target.settings = { ...cfg.tiktok };
      }
      if (cfg.customizeText) {
        target.content_override = cfg.customText;
      } else if (initialOverrideIds.has(ch.id)) {
        target.content_override = null;
      }
      return target;
    });
  }

  async function handleSaveSet() {
    setApiError(null);
    setSetFeedback(null);
    const trimmedName = setName.trim();
    if (!trimmedName) {
      setApiError({ message: t("publications.editor.setNameRequired"), errors: [] });
      return;
    }
    if (selectedChannels.length === 0) {
      setApiError({
        message: t("publications.editor.setNeedsChannel"),
        errors: [],
      });
      return;
    }

    try {
      const saved = await createSetMutation.mutateAsync({
        name: trimmedName,
        content: content || null,
        media: serializeMedia(selectedMedia),
        targets: buildTargetsPayload(),
      });
      setSavingSetOpen(false);
      setSetName("");
      setSetFeedback(t("publications.editor.setSaved", { name: saved.name }));
    } catch (err) {
      setApiError(parsePublicationError(err, t("publications.editor.setSaveFailed")));
    }
  }

  async function submitSetMode() {
    setApiError(null);
    const trimmedName = setName.trim();
    if (!trimmedName) {
      setApiError({ message: t("publications.editor.setNameRequired"), errors: [] });
      return;
    }
    if (selectedChannels.length === 0) {
      setApiError({
        message: t("publications.editor.setNeedsChannel"),
        errors: [],
      });
      return;
    }

    const payload = {
      name: trimmedName,
      content: content || null,
      media: serializeMedia(selectedMedia),
      targets: buildTargetsPayload(),
    };

    try {
      if (initialSet) {
        await updateSetMutation.mutateAsync({
          id: initialSet.id,
          patch: payload,
        });
      } else {
        await createSetMutation.mutateAsync(payload);
      }
      onClose();
    } catch (err) {
      setApiError(parsePublicationError(err, t("publications.editor.setSaveFailed")));
    }
  }

  async function submitPublication(asDraft: boolean) {
    setSubmitAttempted(true);
    setApiError(null);

    if (ruleProblems.length > 0) {
      return;
    }

    let isoScheduled: string | null | undefined;
    if (whenMode === "schedule") {
      const parsed = fromDatetimeLocalInput(scheduledFor);
      if (!parsed && !asDraft) {
        setApiError({
          message: t("publications.editor.invalidSchedule"),
          errors: [],
        });
        return;
      }
      if (parsed && !asDraft && new Date(parsed).getTime() < Date.now() - 60_000) {
        const when = new Date(parsed).toLocaleString(INTL_TAGS[locale], {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        });
        setApiError({
          message: t("publications.editor.pastSchedule", { when }),
          errors: [],
        });
        return;
      }
      isoScheduled = parsed ?? null;
    } else {
      isoScheduled = initial ? null : undefined;
    }

    const payload = {
      content: content || null,
      media: serializeMedia(selectedMedia),
      ...(isoScheduled !== undefined ? { scheduled_for: isoScheduled } : {}),
      draft: asDraft,
      targets: buildTargetsPayload(),
    };

    try {
      if (initial) {
        await updateMutation.mutateAsync({
          id: initial.id,
          patch: payload,
        });
      } else {
        await createMutation.mutateAsync(payload);
      }
      onClose();
    } catch (err) {
      setApiError(
        parsePublicationError(err, t("publications.editor.saveFailed")),
      );
    }
  }

  if (!open) return null;

  const sets = setsQuery.data ?? [];
  const signatures = signaturesQuery.data ?? [];
  const libraryItems: MediaAsset[] =
    libraryQuery.data?.pages.flatMap((p) => p) ?? [];

  const dialogTitle = isSetMode
    ? initialSet
      ? t("publications.editor.editSet")
      : t("publications.editor.addSet")
    : initial
      ? t("publications.editor.editTitle")
      : t("publications.newPublication");

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="publication-editor-title"
      className="max-h-[92dvh] w-full max-w-3xl overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop backdrop:opacity-80"
    >
      <div className="space-y-5 p-5">
        {/* Header + Sets toolbar */}
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-glass pb-3">
          <div>
            <h2
              id="publication-editor-title"
              className="text-lg font-medium text-fg"
            >
              {dialogTitle}
            </h2>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!isSetMode && initial && onOpenDetail ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onOpenDetail(initial)}
              >
                <Eye className="h-4 w-4" aria-hidden />
                {t("publications.editor.view")}
              </Button>
            ) : null}

            {!isSetMode && sets.length > 0 ? (
              <div className="relative">
                <Button
                  type="button"
                  size="sm"
                  variant="simple"
                  aria-expanded={setsOpen}
                  onClick={() => {
                    setSetsOpen((o) => !o);
                    setSavingSetOpen(false);
                  }}
                >
                  <FolderOpen className="h-4 w-4" aria-hidden />
                  {t("publications.editor.useSet")}
                </Button>
                {setsOpen ? (
                  <div
                    role="menu"
                    aria-label={t("publications.editor.savedSets")}
                    className="absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-md border border-glass bg-surface-2 py-1 shadow-menu"
                  >
                    {sets.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        role="menuitem"
                        onClick={() => applySet(s)}
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-fg hover:bg-hover-glass"
                      >
                        <span className="truncate">{s.name}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {!isSetMode && isAdmin ? (
              <Button
                type="button"
                size="sm"
                variant="simple"
                onClick={() => {
                  setSavingSetOpen((o) => !o);
                  setSetsOpen(false);
                }}
              >
                <Bookmark className="h-4 w-4" aria-hidden />
                {t("publications.editor.saveAsSet")}
              </Button>
            ) : null}

            <button
              type="button"
              aria-label={t("actions.closeDialog")}
              onClick={onClose}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>

        {/* Save-as-set inline box (publication mode) */}
        {!isSetMode && savingSetOpen ? (
          <div className="flex flex-wrap items-end gap-2 rounded-md border border-glass bg-surface-2 p-3">
            <div className="min-w-[200px] flex-1 space-y-1">
              <Label htmlFor="pub-set-name" required>
                {t("publications.editor.setName")}
              </Label>
              <Input
                id="pub-set-name"
                value={setName}
                onChange={(e) => setSetName(e.target.value)}
                placeholder={t("publications.editor.setNamePlaceholder")}
              />
            </div>
            <Button
              type="button"
              size="sm"
              loading={createSetMutation.isPending}
              onClick={() => void handleSaveSet()}
            >
              {t("publications.editor.saveSet")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setSavingSetOpen(false)}
            >
              {t("actions.cancel")}
            </Button>
          </div>
        ) : null}

        {setFeedback ? (
          <p
            role="status"
            className="rounded-md border border-success bg-surface-2 px-3 py-2 text-xs text-success"
          >
            {setFeedback}
          </p>
        ) : null}

        <div ref={errorRef}>
          <PublicationErrorAlert
            error={apiError}
            onDismiss={() => setApiError(null)}
          />
        </div>

        {/* Nombre del set (set mode) */}
        {isSetMode ? (
          <div className="space-y-1.5">
            <Label htmlFor="pub-editor-set-name" required>
              {t("publications.editor.setName")}
            </Label>
            <Input
              id="pub-editor-set-name"
              value={setName}
              maxLength={120}
              onChange={(e) => setSetName(e.target.value)}
              placeholder={t("publications.editor.setNamePlaceholder")}
            />
          </div>
        ) : null}

        {/* Canales */}
        <div className="space-y-2">
          <Label required>{t("conversations.tabs.channels")}</Label>
          {activeChannels.length === 0 ? (
            <p className="rounded-md border border-glass bg-field px-3 py-2.5 text-xs text-fg-muted">
              {t("publications.editor.noActiveChannels")}
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {activeChannels.map((ch) => {
                const selected = selectedChannelIds.includes(ch.id);
                const name = channelDisplayName(ch);
                return (
                  <button
                    key={ch.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleChannel(ch.id)}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-control border px-3 py-1.5 text-sm transition-colors",
                      "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                      selected
                        ? "border-neon bg-focused font-medium text-lit"
                        : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
                    )}
                  >
                    <ChannelAvatar channel={ch} size="sm" />
                    <span>{name}</span>
                    {selected ? (
                      <Check className="h-3.5 w-3.5 text-neon" aria-hidden />
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Texto compartido + Firma + Contador */}
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor="pub-content">{t("publications.editor.text")}</Label>
            <div className="flex items-center gap-3">
              <div className="relative">
                <button
                  type="button"
                  aria-expanded={signaturesOpen}
                  onClick={() => setSignaturesOpen((o) => !o)}
                  className="inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                >
                  <FileSignature className="h-3.5 w-3.5" aria-hidden />
                  {t("publications.editor.signature")}
                </button>
                {signaturesOpen ? (
                  <div
                    role="menu"
                    aria-label={t("publications.editor.availableSignatures")}
                    className="absolute right-0 z-30 mt-1 w-64 overflow-hidden rounded-md border border-glass bg-surface-2 py-1 shadow-menu"
                  >
                    {signatures.length === 0 ? (
                      <p className="px-3 py-2 text-xs text-fg-muted">
                        {t("publications.editor.noSignatures")}
                      </p>
                    ) : (
                      signatures.map((sig) => (
                        <button
                          key={sig.id}
                          type="button"
                          role="menuitem"
                          onClick={() => appendSignature(sig.content)}
                          className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-xs text-fg hover:bg-hover-glass"
                        >
                          <span className="line-clamp-2 whitespace-pre-wrap">
                            {sig.content}
                          </span>
                          {sig.auto_add ? (
                            <span className="text-[10px] text-lit">
                              {t("publications.editor.automatic")}
                            </span>
                          ) : null}
                        </button>
                      ))
                    )}
                  </div>
                ) : null}
              </div>

              <span
                data-testid="shared-char-counter"
                className={cn(
                  "font-numeric text-xs tabular-nums",
                  sharedLimit !== null && sharedLength > sharedLimit.limit
                    ? "font-semibold text-danger"
                    : "text-fg-muted",
                )}
              >
                {sharedLimit !== null
                  ? `${sharedLength} / ${sharedLimit.limit}`
                  : `${sharedLength} caracteres`}
              </span>
            </div>
          </div>

          <Textarea
            id="pub-content"
            rows={4}
            value={content}
            onChange={(e) => {
              autoSigAppliedRef.current = true;
              setContent(e.target.value);
            }}
            placeholder={t("publications.editor.contentPlaceholder")}
          />
        </div>

        {/* Medios */}
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label>
              {t("publications.editor.mediaCount", { count: selectedMedia.length })}
            </Label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*,video/*"
                aria-label={t("publications.editor.uploadNewFile")}
                className="hidden"
                tabIndex={-1}
                onChange={(e) => {
                  void handleUploadFiles(e.target.files);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                size="sm"
                variant="simple"
                onClick={() => setLibraryOpen((o) => !o)}
              >
                <Images className="h-4 w-4" aria-hidden />
                {libraryOpen ? t("publications.editor.closeLibrary") : t("publications.editor.pickFromLibrary")}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                loading={uploadMediaMutation.isPending}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4" aria-hidden />
                {uploadMediaMutation.isPending ? t("publications.media.uploading") : t("publications.editor.uploadNew")}
              </Button>
            </div>
          </div>

          {/* Selected media in order */}
          {selectedMedia.length > 0 ? (
            <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {selectedMedia.map((m, idx) => (
                <li
                  key={`${m.media_id ?? m.url}-${idx}`}
                  className="flex items-center gap-2.5 rounded-md border border-glass bg-surface-2 p-2"
                >
                  <span className="font-numeric text-xs font-semibold tabular-nums text-fg-muted">
                    {idx + 1}.
                  </span>
                  <div className="h-12 w-12 shrink-0 overflow-hidden rounded-sm border border-glass bg-field">
                    {m.type === "video" ? (
                      <video
                        src={m.url}
                        preload="metadata"
                        muted
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={m.url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-fg">
                      {m.filename ||
                        (m.type === "video" ? t("publications.media.video") : t("publications.media.image")) +
                          (m.media_id ? ` #${m.media_id}` : "")}
                    </p>
                    <p className="text-[11px] uppercase text-fg-muted">
                      {m.type === "video" ? t("publications.media.video") : t("publications.media.image")}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={t("publications.editor.moveMediaBefore", { n: idx + 1 })}
                      title={t("publications.editor.moveBefore")}
                      disabled={idx === 0}
                      onClick={() => moveMedia(idx, -1)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-35"
                    >
                      <ArrowUp className="h-3.5 w-3.5" aria-hidden />
                    </button>
                    <button
                      type="button"
                      aria-label={t("publications.editor.moveMediaAfter", { n: idx + 1 })}
                      title={t("publications.editor.moveAfter")}
                      disabled={idx === selectedMedia.length - 1}
                      onClick={() => moveMedia(idx, 1)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-35"
                    >
                      <ArrowDown className="h-3.5 w-3.5" aria-hidden />
                    </button>
                    <button
                      type="button"
                      aria-label={t("publications.editor.removeMedia", { n: idx + 1 })}
                      title={t("common.remove")}
                      onClick={() => removeMedia(idx)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-sm text-fg-muted hover:bg-hover-glass hover:text-danger"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          ) : null}

          {/* Library inline picker */}
          {libraryOpen ? (
            <div className="space-y-3 rounded-md border border-glass bg-surface-2 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium text-fg">
                  {t("publications.editor.mediaLibrary")}
                </span>
                <SegmentedControl
                  ariaLabel={t("publications.editor.filterLibrary")}
                  size="sm"
                  value={libraryKind}
                  onValueChange={setLibraryKind}
                  options={MEDIA_PICKER_FILTERS.map((o) => ({
                    ...o,
                    label: t(o.label),
                  }))}
                />
              </div>

              {libraryQuery.isLoading ? (
                <p className="py-6 text-center text-xs text-fg-muted">
                  {t("publications.editor.loadingLibrary")}
                </p>
              ) : libraryItems.length === 0 ? (
                <p className="py-6 text-center text-xs text-fg-muted">
                  {t("publications.editor.emptyLibrary")}
                </p>
              ) : (
                <div className="grid max-h-56 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-5">
                  {libraryItems.map((asset) => {
                    const picked = selectedMedia.some(
                      (m) => m.media_id === asset.id,
                    );
                    const label =
                      asset.filename ||
                      t("publications.editor.mediaNumber", { id: asset.id });
                    return (
                      <button
                        key={asset.id}
                        type="button"
                        aria-label={t("publications.editor.pick", { name: label })}
                        aria-pressed={picked}
                        onClick={() => toggleLibraryAsset(asset)}
                        className={cn(
                          "relative aspect-square overflow-hidden rounded-md border bg-field text-left transition-colors",
                          picked ? "border-neon ring-2 ring-neon" : "border-glass",
                        )}
                      >
                        {asset.kind === "video" ? (
                          <>
                            <video
                              src={asset.url}
                              preload="metadata"
                              muted
                              className="h-full w-full object-cover"
                            />
                            <span className="absolute left-1 top-1 rounded-sm bg-backdrop px-1 py-0.5 text-[9px] uppercase text-white">
                              <Film className="inline h-2.5 w-2.5" aria-hidden />
                            </span>
                          </>
                        ) : (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={asset.url}
                            alt={label}
                            className="h-full w-full object-cover"
                          />
                        )}
                        {picked ? (
                          <span className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-neon text-white">
                            <Check className="h-3 w-3" aria-hidden />
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              )}

              {libraryQuery.hasNextPage ? (
                <div className="flex justify-center">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    loading={libraryQuery.isFetchingNextPage}
                    onClick={() => libraryQuery.fetchNextPage()}
                  >
                    {t("publications.media.loadMore")}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Por canal */}
        {selectedChannels.length > 0 ? (
          <div className="space-y-2.5">
            <Label>{t("publications.editor.perChannel")}</Label>
            <div className="space-y-2.5">
              {selectedChannels.map((ch) => {
                const cfg = configFor(ch.id);
                const name = channelDisplayName(ch);
                const ownLimit = channelCharLimit(ch.network, selectedMedia);
                const ownLength = textLength(ch.network, cfg.customText);

                return (
                  <div
                    key={ch.id}
                    className="space-y-2.5 rounded-md border border-glass bg-surface-2 p-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <NetworkIcon network={ch.network} />
                        <span className="text-sm font-medium text-fg">
                          {name}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {ch.network === "instagram" ? (
                          <SegmentedControl
                            ariaLabel={t("publications.editor.typeIn", { name })}
                            size="sm"
                            value={cfg.postType}
                            onValueChange={(next) =>
                              updateConfig(ch.id, { postType: next })
                            }
                            options={IG_POST_TYPES}
                          />
                        ) : null}

                        <button
                          type="button"
                          aria-pressed={cfg.customizeText}
                          onClick={() =>
                            updateConfig(ch.id, {
                              customizeText: !cfg.customizeText,
                              customText:
                                !cfg.customizeText && !cfg.customText
                                  ? content
                                  : cfg.customText,
                            })
                          }
                          className={cn(
                            "rounded-control border px-2.5 py-1 text-xs font-medium transition-colors",
                            cfg.customizeText
                              ? "border-neon bg-focused text-lit"
                              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
                          )}
                        >
                          {t("publications.editor.customizeText")}
                        </button>
                      </div>
                    </div>

                    {ch.network === "tiktok" ? (
                      <TikTokTargetSettings
                        accountId={accountId}
                        channel={ch}
                        value={cfg.tiktok}
                        photosOnly={
                          selectedMedia.length > 0 &&
                          selectedMedia.every((m) => m.type === "image")
                        }
                        videoUrl={
                          selectedMedia.find((m) => m.type === "video")?.url ??
                          null
                        }
                        onChange={(patch) =>
                          updateConfig(ch.id, {
                            tiktok: { ...cfg.tiktok, ...patch },
                          })
                        }
                        onProblemChange={(problem) =>
                          reportPanelProblem(ch.id, problem)
                        }
                      />
                    ) : null}

                    {ch.network === "instagram" && cfg.postType === "story" ? (
                      <p className="text-xs text-fg-muted">
                        {t("publications.editor.storyNoText")}
                      </p>
                    ) : null}

                    {cfg.customizeText ? (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-fg-muted">
                          <Label htmlFor={`override-${ch.id}`}>
                            {t("publications.editor.textFor", { name })}
                          </Label>
                          {ownLimit !== null ? (
                            <span
                              className={cn(
                                "font-numeric tabular-nums",
                                ownLength > ownLimit &&
                                  "font-semibold text-danger",
                              )}
                            >
                              {ownLength} / {ownLimit}
                            </span>
                          ) : null}
                        </div>
                        <Textarea
                          id={`override-${ch.id}`}
                          rows={3}
                          value={cfg.customText}
                          onChange={(e) =>
                            updateConfig(ch.id, { customText: e.target.value })
                          }
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {/* Cuándo (publication mode only) */}
        {!isSetMode ? (
          <div className="space-y-2">
            <Label>{t("publications.editor.when")}</Label>
            <div className="flex flex-wrap items-center gap-3">
              <SegmentedControl
                ariaLabel={t("publications.editor.whenLabel")}
                size="sm"
                value={whenMode}
                onValueChange={setWhenMode}
                options={[
                  { value: "now" as WhenMode, label: t("publications.editor.publishNow") },
                  { value: "schedule" as WhenMode, label: t("publications.editor.schedule") },
                ]}
              />
              {whenMode === "schedule" ? (
                <Input
                  id="pub-scheduled-for"
                  aria-label={t("publications.editor.scheduleAt")}
                  type="datetime-local"
                  value={scheduledFor}
                  // The picker then offers only times from now on.
                  min={toDatetimeLocalInput(new Date())}
                  onChange={(e) => setScheduledFor(e.target.value)}
                  className="w-auto tabular-nums"
                />
              ) : null}
            </div>
            {whenMode === "schedule" && scheduledHint ? (
              <p
                className={cn(
                  "text-xs",
                  scheduledHint.past ? "text-danger" : "text-fg-muted",
                )}
              >
                {scheduledHint.text}
              </p>
            ) : null}
          </div>
        ) : null}

        {/* Vista previa simple por canal */}
        {selectedChannels.length > 0 ? (
          <div className="space-y-2">
            <Label>{t("publications.editor.preview")}</Label>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {selectedChannels.map((ch) => {
                const cfg = configFor(ch.id);
                const name = channelDisplayName(ch);
                const previewText = cfg.customizeText
                  ? cfg.customText
                  : content;
                const firstMedia = selectedMedia[0];
                const isStory =
                  ch.network === "instagram" && cfg.postType === "story";

                return (
                  <div
                    key={ch.id}
                    className="space-y-2 rounded-md border border-glass bg-field p-3 text-xs"
                  >
                    <div className="flex items-center gap-1.5 font-medium text-fg">
                      <NetworkIcon network={ch.network} />
                      <span className="truncate">{name}</span>
                      {ch.network === "instagram" ? (
                        <span className="ml-auto rounded-sm bg-surface-2 px-1.5 py-0.5 text-[10px] uppercase text-fg-muted">
                          {cfg.postType}
                        </span>
                      ) : null}
                    </div>
                    {firstMedia ? (
                      <div className="h-28 overflow-hidden rounded-sm border border-glass bg-surface">
                        {firstMedia.type === "video" ? (
                          <video
                            src={firstMedia.url}
                            preload="metadata"
                            muted
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={firstMedia.url}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                        )}
                      </div>
                    ) : null}
                    {isStory ? (
                      <p className="italic text-fg-muted">
                        {t("publications.editor.storyNoVisibleText")}
                      </p>
                    ) : previewText.trim() ? (
                      <p className="line-clamp-4 whitespace-pre-wrap break-words text-fg">
                        {previewText}
                      </p>
                    ) : (
                      <p className="italic text-fg-muted">{t("publications.noText")}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        {/* Rule warnings / errors before submit */}
        {!isSetMode && ruleProblems.length > 0 ? (
          <div
            role={submitAttempted ? "alert" : "status"}
            className={cn(
              "rounded-md border bg-surface-2 px-3 py-2 text-xs",
              submitAttempted
                ? "border-danger text-danger"
                : "border-warning text-warning",
            )}
          >
            <p className="font-medium">{t("publications.editor.checkRules")}</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {ruleProblems.map((prob, idx) => (
                <li key={idx}>{prob}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {!isSetMode && xLinkChannels.length > 0 ? (
          <p
            role="status"
            className="rounded-md border border-glass bg-surface-2 px-3 py-2 text-xs text-fg-muted"
          >
            {t("publications.editor.xLinkCost", {
              channels: xLinkChannels.join(", "),
            })}
          </p>
        ) : null}

        {!isSetMode ? (
          <TikTokConsent
            settings={selectedChannels
              .filter((ch) => ch.network === "tiktok")
              .map((ch) => configFor(ch.id).tiktok)}
          />
        ) : null}

        {/* Actions */}
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-glass pt-3">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
          >
            {t("actions.cancel")}
          </Button>
          {isSetMode ? (
            <Button
              type="button"
              loading={isSubmitting}
              onClick={() => void submitSetMode()}
            >
              {t("publications.editor.saveSet")}
            </Button>
          ) : (
            <>
              <Button
                type="button"
                variant="secondary"
                loading={isSubmitting}
                onClick={() => void submitPublication(true)}
              >
                {t("publications.editor.saveDraft")}
              </Button>
              {/* A disabled button gets no hover events: the wrapper carries
                  the reason. */}
              <span title={disclosureBlock ?? undefined}>
                <Button
                  type="button"
                  loading={isSubmitting}
                  disabled={disclosureBlock !== null}
                  onClick={() => void submitPublication(false)}
                >
                  {whenMode === "schedule" ? t("publications.editor.schedule") : t("publications.editor.publishNow")}
                </Button>
              </span>
            </>
          )}
        </div>
      </div>
    </dialog>
  );
}
