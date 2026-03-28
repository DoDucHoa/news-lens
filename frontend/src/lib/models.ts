export const DEFAULT_LLM_MODEL = "qwen3.5:0.8b";

export const ALLOWED_LLM_MODELS = [
  "qwen3.5:0.8b",
  "qwen3.5:2b",
  "qwen3.5:4b",
] as const;

export type LlmModel = (typeof ALLOWED_LLM_MODELS)[number];

export const SELECTED_MODEL_STORAGE_KEY = "newslens:selected-llm-model:v1";

export function isAllowedLlmModel(value: unknown): value is LlmModel {
  return typeof value === "string" && ALLOWED_LLM_MODELS.includes(value as LlmModel);
}
