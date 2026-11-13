"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  AUTOMATION_EVENT_LABELS,
  AUTOMATION_EVENTS,
  type AutomationActionName,
  type AutomationEvent,
  type AutomationRule,
  type AutomationRuleInput,
  type FilterOperator,
  OPERATORS_WITHOUT_VALUES,
  type RuleCondition,
  STANDARD_ATTRIBUTES,
} from "@/lib/api/automation-rules";

import {
  paramsToText,
  textToParams,
} from "../shared/action-meta";
import { AutomationActionRow } from "./automation-action-row";
import {
  type ConditionDraft,
  ConditionRow,
  valuesFromText,
  valuesToText,
} from "./condition-row";
import { useT } from "@/lib/i18n/provider";

type ActionDraft = { action_name: AutomationActionName; text: string };

export function AutomationRuleForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: AutomationRule;
  submitting?: boolean;
  onSubmit: (input: AutomationRuleInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [eventName, setEventName] = useState<AutomationEvent>(
    initial?.event_name ?? "conversation_created",
  );
  const [active, setActive] = useState(initial?.active ?? true);
  const [conditions, setConditions] = useState<ConditionDraft[]>(
    (initial?.conditions ?? []).map((c) => ({
      attribute_key: c.attribute_key,
      filter_operator: c.filter_operator,
      query_operator: c.query_operator,
      valuesText: valuesToText(c.values),
      custom_attribute_type: c.custom_attribute_type ?? null,
    })),
  );
  const [actions, setActions] = useState<ActionDraft[]>(
    (initial?.actions ?? []).map((a) => ({
      action_name: a.action_name,
      text: paramsToText(a.action_name, a.action_params),
    })),
  );
  const [error, setError] = useState<string | null>(null);

  function addCondition() {
    setConditions((prev) => [
      ...prev,
      {
        attribute_key: STANDARD_ATTRIBUTES[0].key,
        filter_operator: "equal_to" as FilterOperator,
        query_operator: "AND",
        valuesText: "",
      },
    ]);
  }

  function addAction() {
    setActions((prev) => [...prev, { action_name: "send_message", text: "" }]);
  }

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("profile.nameRequired"));
    if (actions.length === 0)
      return setError(t("settingsMacros.needAction"));

    const wireConditions: RuleCondition[] = conditions.map((c, i) => ({
      attribute_key: c.attribute_key,
      filter_operator: c.filter_operator,
      query_operator: i === conditions.length - 1 ? "" : c.query_operator,
      values: OPERATORS_WITHOUT_VALUES.has(c.filter_operator)
        ? []
        : valuesFromText(c.valuesText),
      ...(c.custom_attribute_type
        ? { custom_attribute_type: c.custom_attribute_type }
        : {}),
    }));

    const input: AutomationRuleInput = {
      name: name.trim(),
      description: description.trim() || null,
      event_name: eventName,
      active,
      conditions: wireConditions,
      actions: actions.map((a) => ({
        action_name: a.action_name,
        action_params: textToParams(a.action_name, a.text),
      })),
    };

    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsAutomation.saveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="ar-name" required>
          {t("profile.name")}
        </Label>
        <Input
          id="ar-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ar-desc">{t("products.description")}</Label>
        <Textarea
          id="ar-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ar-event">{t("settingsNotif.event")}</Label>
        <select
          id="ar-event"
          className={selectClassName()}
          value={eventName}
          onChange={(e) => setEventName(e.target.value as AutomationEvent)}
        >
          {AUTOMATION_EVENTS.map((ev) => (
            <option key={ev} value={ev}>
              {t(AUTOMATION_EVENT_LABELS[ev])}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
          className="h-4 w-4 rounded border-glass accent-neon"
        />
        {t("settingsAutomation.active")}
      </label>

      <div className="space-y-2">
        <Label>{t("settingsAutomation.conditions")}</Label>
        {conditions.length === 0 ? (
          <p className="text-sm text-fg-muted">
            {t("settingsAutomation.noConditionsHint")}
          </p>
        ) : (
          <div className="space-y-2">
            {conditions.map((c, i) => (
              <ConditionRow
                key={i}
                index={i}
                total={conditions.length}
                value={c}
                onChange={(next) =>
                  setConditions((prev) =>
                    prev.map((x, j) => (j === i ? next : x)),
                  )
                }
                onRemove={() =>
                  setConditions((prev) => prev.filter((_, j) => j !== i))
                }
              />
            ))}
          </div>
        )}
        <Button type="button" variant="ghost" size="sm" onClick={addCondition}>
          <Plus className="h-4 w-4" aria-hidden />
          {t("settingsAutomation.addCondition")}
        </Button>
      </div>

      <div className="space-y-2">
        <Label>{t("settingsMacros.actions")}</Label>
        {actions.length === 0 ? (
          <p className="text-sm text-fg-muted">
            {t("settingsMacros.needAction")}
          </p>
        ) : (
          <div className="space-y-2">
            {actions.map((a, i) => (
              <AutomationActionRow
                key={i}
                value={a}
                onChange={(next) =>
                  setActions((prev) =>
                    prev.map((x, j) => (j === i ? next : x)),
                  )
                }
                onRemove={() =>
                  setActions((prev) => prev.filter((_, j) => j !== i))
                }
              />
            ))}
          </div>
        )}
        <Button type="button" variant="ghost" size="sm" onClick={addAction}>
          <Plus className="h-4 w-4" aria-hidden />
          {t("settingsMacros.addAction")}
        </Button>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsAutomation.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
