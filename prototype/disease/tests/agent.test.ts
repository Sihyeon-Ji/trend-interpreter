import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { evidenceBriefing } from "../src/lib/briefing";
import { dataset, report } from "./fixtures";

const mocks = vi.hoisted(() => ({ generateContent: vi.fn() }));
vi.mock("@google/genai", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@google/genai")>()),
  GoogleGenAI: class {
    models = { generateContent: mocks.generateContent };
  },
}));

beforeEach(() => {
  vi.stubEnv("GEMINI_API_KEY", "test-only-key");
  mocks.generateContent.mockReset();
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("bounded Gemini investigation", () => {
  it("completes a tool round, returns cited findings, and records actual steps", async () => {
    const call = {
      name: "read_report",
      args: { reportId: report.id },
      id: "call-1",
    };
    mocks.generateContent
      .mockResolvedValueOnce({
        functionCalls: [call],
        candidates: [
          { content: { role: "model", parts: [{ functionCall: call }] } },
        ],
      })
      .mockResolvedValueOnce({
        text: "Evidence gathered.",
        candidates: [
          {
            content: { role: "model", parts: [{ text: "Evidence gathered." }] },
          },
        ],
      })
      .mockResolvedValueOnce({
        text: JSON.stringify(evidenceBriefing([report], dataset)),
      });
    const { runBriefingAgent } = await import("../src/lib/agent");
    const result = await runBriefingAgent(
      [report],
      dataset,
      "Review these reports.",
    );
    expect(result.mode).toBe("gemini");
    expect(result.steps).toContain(`Read official report: ${report.title}`);
    expect(result.steps).toContain("Validated all source references");
    expect(mocks.generateContent).toHaveBeenCalledTimes(3);
    const toolResponse = mocks.generateContent.mock.calls[1][0].contents.find(
      (content: { parts: { functionResponse?: unknown }[] }) =>
        content.parts.some((part) => part.functionResponse),
    );
    expect(toolResponse.parts[0].functionResponse.response.result.id).toBe(
      report.id,
    );
  });
  it("fails a paid analysis if the final model output cites an unknown report", async () => {
    const draft = evidenceBriefing([report], dataset);
    draft.observations[0].reportIds = ["fabricated-source"];
    mocks.generateContent
      .mockResolvedValueOnce({ text: "Ready" })
      .mockResolvedValueOnce({ text: JSON.stringify(draft) });
    const { runBriefingAgent } = await import("../src/lib/agent");
    await expect(runBriefingAgent([report], dataset, "Review")).rejects.toThrow(
      "unsupported source reference",
    );
  });
  it("does not call Gemini at all without a key", async () => {
    vi.stubEnv("GEMINI_API_KEY", "");
    const { runBriefingAgent } = await import("../src/lib/agent");
    expect((await runBriefingAgent([report], dataset, "Review")).mode).toBe(
      "evidence",
    );
    expect(mocks.generateContent).not.toHaveBeenCalled();
  });
});
