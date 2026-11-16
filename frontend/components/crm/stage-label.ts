import type { Pipeline, Stage } from "@/lib/api/crm";
import { type Translate, translateOr } from "@/lib/i18n/translate";

/** A stage someone named shows that name; a seeded one is named by its
 *  ``code`` in the reader's language. */
export function stageLabel(t: Translate, stage: Pick<Stage, "name" | "code">): string {
  if (stage.name) return stage.name;
  if (stage.code) return translateOr(t, `opportunities.stages.${stage.code}`, stage.code); // i18n-ignore
  return "—";
}

export function pipelineLabel(t: Translate, pipeline: Pick<Pipeline, "name">): string {
  return pipeline.name || t("opportunities.salesPipeline");
}
