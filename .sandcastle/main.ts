import * as sandcastle from "@ai-hero/sandcastle";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

type Role = "planner" | "developer" | "reviewer" | "merger";

const role = resolveRole();
const repoPath = process.env.SOFTWARE_FACTORY_REPOSITORY_PATH ?? process.cwd();
const templatePath = path.join(process.cwd(), ".sandcastle", "prompts", `${role}.md`);
const template = await fs.readFile(templatePath, "utf8");
const prompt = renderTemplate(template, buildTemplateValues(role));

await sandcastle.run({
  name: buildRunName(role),
  agent: createAgent(),
  sandbox: createSandbox(),
  cwd: repoPath,
  prompt,
});

function resolveRole(): Role {
  const candidate = (process.argv[2] ?? process.env.SOFTWARE_FACTORY_ROLE ?? "").trim().toLowerCase();
  if (candidate === "planner" || candidate === "developer" || candidate === "reviewer" || candidate === "merger") {
    return candidate;
  }
  throw new Error(`Unsupported Sandcastle role: ${candidate || "<empty>"}`);
}

function buildRunName(role: Role): string {
  const suffix =
    process.env.SOFTWARE_FACTORY_ISSUE_NUMBER ?? process.env.SOFTWARE_FACTORY_PULL_REQUEST_NUMBER ?? "system";
  return `software-factory-${role}-${suffix}`;
}

function createAgent() {
  const agentName = (process.env.SOFTWARE_FACTORY_SANDCASTLE_AGENT ?? "codex").trim().toLowerCase();
  if (agentName === "claude" || agentName === "claude-code" || agentName === "claudecode") {
    return sandcastle.claudeCode({ permissionMode: "auto" });
  }
  if (agentName === "codex") {
    return sandcastle.codex();
  }
  throw new Error(`Unsupported Sandcastle agent: ${agentName}`);
}

function createSandbox() {
  const sandboxName = (process.env.SOFTWARE_FACTORY_SANDCASTLE_SANDBOX ?? "no-sandbox").trim().toLowerCase();
  if (sandboxName === "podman") {
    return sandcastle.podman();
  }
  if (sandboxName === "docker") {
    return sandcastle.docker();
  }
  return sandcastle.noSandbox();
}

function buildTemplateValues(role: Role): Record<string, string> {
  const outputHint =
    role === "planner"
      ? buildPlannerOutputHint()
      : role === "developer"
        ? buildDeveloperOutputHint()
        : role === "reviewer"
          ? buildReviewerOutputHint()
          : buildMergerOutputHint();

  return {
    context_block: buildContextBlock(),
    output_hint: outputHint,
    repository_path: process.env.SOFTWARE_FACTORY_REPOSITORY_PATH ?? process.cwd(),
    repository_full_name: process.env.SOFTWARE_FACTORY_REPOSITORY_FULL_NAME ?? "",
    default_branch: process.env.SOFTWARE_FACTORY_DEFAULT_BRANCH ?? "main",
    role,
  };
}

function buildContextBlock(): string {
  const sections: Array<[string, string | undefined]> = [
    ["Repository", process.env.SOFTWARE_FACTORY_REPOSITORY_FULL_NAME],
    ["Repository Path", process.env.SOFTWARE_FACTORY_REPOSITORY_PATH],
    ["Default Branch", process.env.SOFTWARE_FACTORY_DEFAULT_BRANCH],
    ["Branch", process.env.SOFTWARE_FACTORY_BRANCH_NAME],
    ["Issue Number", process.env.SOFTWARE_FACTORY_ISSUE_NUMBER],
    ["Issue Title", process.env.SOFTWARE_FACTORY_ISSUE_TITLE],
    ["Issue Body", process.env.SOFTWARE_FACTORY_ISSUE_BODY],
    ["Plan ID", process.env.SOFTWARE_FACTORY_PLAN_ID],
    ["Plan Artifact", process.env.SOFTWARE_FACTORY_PLAN_ARTIFACT_PATH],
    ["Pull Request Number", process.env.SOFTWARE_FACTORY_PULL_REQUEST_NUMBER],
    ["Pull Request Title", process.env.SOFTWARE_FACTORY_PULL_REQUEST_TITLE],
    ["Pull Request Body", process.env.SOFTWARE_FACTORY_PULL_REQUEST_BODY],
    ["Review Output Path", process.env.SOFTWARE_FACTORY_REVIEW_OUTPUT_PATH],
    ["Merge Output Path", process.env.SOFTWARE_FACTORY_MERGE_OUTPUT_PATH],
  ];

  return sections
    .filter(([, value]) => Boolean(value && value.trim().length > 0))
    .map(([label, value]) => `- ${label}: ${value}`)
    .join("\n");
}

function buildPlannerOutputHint(): string {
  const outputPath = process.env.SOFTWARE_FACTORY_PLAN_ARTIFACT_PATH;
  if (!outputPath) {
    return "Update the plan in chat output only; no plan artifact path was provided.";
  }
  return `Write or update a Markdown implementation plan at ${outputPath}.`;
}

function buildDeveloperOutputHint(): string {
  return [
    "Modify code in the current repository workspace to address the issue.",
    "Do not create commits, push branches, or create pull requests; the Python control plane does that after you finish.",
    "Run the smallest relevant checks you can inside the workspace and leave the working tree with the desired code changes.",
  ].join(" ");
}

function buildReviewerOutputHint(): string {
  const outputPath = process.env.SOFTWARE_FACTORY_REVIEW_OUTPUT_PATH;
  if (!outputPath) {
    return "Produce a concise review summary in chat output.";
  }
  return `Write a concise Markdown review summary to ${outputPath}.`;
}

function buildMergerOutputHint(): string {
  const outputPath = process.env.SOFTWARE_FACTORY_MERGE_OUTPUT_PATH;
  if (!outputPath) {
    return "Produce a concise merge-readiness summary in chat output.";
  }
  return `Write a concise Markdown merge-readiness summary to ${outputPath}.`;
}

function renderTemplate(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key: string) => values[key] ?? "");
}

