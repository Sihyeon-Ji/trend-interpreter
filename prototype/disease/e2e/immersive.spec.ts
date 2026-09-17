import { expect, test } from "@playwright/test";

test("unified header and borderless full-size globe replace permanent side panels", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator(".earth-view")).toHaveAttribute(
    "data-terrain",
    "ready",
  );
  const header = page.locator(".unified-header");
  await expect(
    header.getByRole("heading", { name: "Global disease monitor" }),
  ).toBeVisible();
  await expect(
    header.getByRole("textbox", { name: "Search reports" }),
  ).toBeVisible();
  await expect(
    header.getByRole("combobox", { name: "Reporting period" }),
  ).toBeVisible();
  await expect(
    page.locator(".planet-context, .intelligence-rail, .hud-popover"),
  ).toHaveCount(0);
  await expect(page.locator(".planet-stage")).toHaveCSS(
    "border-top-width",
    "0px",
  );
  expect(
    (await page.locator(".planet-stage").boundingBox())!.width,
  ).toBeGreaterThan(1300);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight > innerHeight,
    ),
  ).toBe(false);
  const canvas = page.locator(".earth-canvas canvas");
  const bounds = await canvas.boundingBox();
  await canvas.click({
    position: { x: bounds!.width / 2, y: bounds!.height / 2 },
  });
  await expect(
    page.getByRole("combobox", { name: "Filter by country" }),
  ).not.toHaveValue("all");
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Latest reports", exact: true })
    .hover();
  await expect(
    page.locator(".hud-popover .incoming-report").first(),
  ).toBeVisible();
  await page.getByRole("heading", { name: "Global disease monitor" }).hover();
  await expect(page.locator(".hud-popover")).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Search reports" })
    .fill("nonexistent-disease-query-xyz");
  await expect(page.locator(".hud-count")).toContainText("0 reports");
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  await page.getByRole("slider", { name: "Observation day" }).fill("0");
  await expect(page.locator(".hud-count")).toContainText("0 reports");
  await page.getByRole("button", { name: "Play timeline" }).click();
  await expect
    .poll(async () =>
      Number(
        await page
          .getByRole("slider", { name: "Observation day" })
          .inputValue(),
      ),
    )
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Pause timeline" }).click();
  await page.getByRole("slider", { name: "Observation day" }).fill("90");
  await page.getByRole("heading", { name: "Global disease monitor" }).click();
  await page.screenshot({
    path: "artifacts/overview-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("scenario settings open on demand, dismiss on Escape, and never resize the globe", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Diseases & scenarios", exact: true })
    .click();
  await expect(page.locator(".earth-view")).toHaveAttribute(
    "data-terrain",
    "ready",
  );
  await expect(
    page.getByRole("combobox", { name: "Scenario origin" }),
  ).toHaveCount(0);
  const before = await page.locator(".planet-render").boundingBox();
  await page
    .getByRole("button", { name: "Scenario controls", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "Scenario origin" }),
  ).toBeVisible();
  expect(await page.locator(".planet-render").boundingBox()).toEqual(before);
  await page.getByRole("slider", { name: "Response strength" }).fill("90");
  await page.getByRole("button", { name: "Faster", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Scenario origin" })
    .selectOption("CN");
  await page
    .getByRole("button", { name: "Close Scenario controls", exact: true })
    .click();
  await expect(page.locator(".hud-popover")).toHaveCount(0);
  await page.getByRole("slider", { name: "Scenario day" }).fill("35");
  const radius = Number(
    await page.locator(".earth-view").getAttribute("data-scenario-radius"),
  );
  await page
    .getByRole("button", { name: "Scenario controls", exact: true })
    .click();
  await page.getByRole("slider", { name: "Response strength" }).fill("30");
  await expect
    .poll(async () =>
      Number(
        await page.locator(".earth-view").getAttribute("data-scenario-radius"),
      ),
    )
    .toBeGreaterThan(radius);
  await page.keyboard.press("Escape");
  await expect(page.locator(".hud-popover")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Scenario controls", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Play timeline" }).click();
  await expect
    .poll(async () =>
      Number(
        await page.getByRole("slider", { name: "Scenario day" }).inputValue(),
      ),
    )
    .toBeGreaterThan(35);
  await page.getByRole("button", { name: "Pause timeline" }).click();
  await page
    .getByRole("button", { name: "Scenario controls", exact: true })
    .click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export scenario settings" }).click();
  expect((await download).suggestedFilename()).toBe(
    "outbreak-atlas-scenario.json",
  );
  await page.getByRole("heading", { name: "Outbreak scenario lab" }).click();
  await page.getByRole("slider", { name: "Scenario day" }).fill("40");
  await page.screenshot({
    path: "artifacts/scenario-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("combobox", { name: "Filter by disease" })
    .selectOption("Dengue");
  await page
    .getByRole("button", { name: "Disease dossier", exact: true })
    .hover();
  await expect(
    page.getByText("Bites from infected mosquitoes", { exact: true }),
  ).toBeVisible();
  await page.getByRole("heading", { name: "Outbreak scenario lab" }).hover();
  await expect(page.locator(".hud-popover")).toHaveCount(0);
});

test("mobile keeps the globe fixed and supports tap-operated overlays", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator(".earth-view")).toHaveAttribute(
    "data-terrain",
    "ready",
  );
  await page.screenshot({
    path: "artifacts/overview-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth > innerWidth ||
        document.documentElement.scrollHeight > innerHeight,
    ),
  ).toBe(false);
  await page
    .getByRole("button", { name: "Diseases & scenarios", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Scenario controls", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Scenario origin" })
    .selectOption("IN");
  await page.getByRole("slider", { name: "Response strength" }).fill("45");
  await page
    .getByRole("button", { name: "Close Scenario controls", exact: true })
    .click();
  await expect(page.locator(".hud-popover")).toHaveCount(0);
  await page.getByRole("slider", { name: "Scenario day" }).fill("40");
  await page.screenshot({
    path: "artifacts/scenario-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth > innerWidth ||
        document.documentElement.scrollHeight > innerHeight,
    ),
  ).toBe(false);
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Generate report", exact: true }),
  ).toBeVisible();
});

test("compatibility globe and source information remain available without WebGL", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      type: string,
      ...args: unknown[]
    ) {
      if (
        type === "webgl" ||
        type === "webgl2" ||
        type === "experimental-webgl"
      )
        return null;
      return original.apply(this, [type, ...args] as Parameters<
        typeof original
      >);
    } as typeof original;
  });
  await page.goto("/");
  await expect(page.locator(".earth-view")).toHaveAttribute(
    "data-renderer",
    "compatibility",
  );
  await page
    .getByRole("combobox", { name: "Filter by country" })
    .selectOption("CD");
  await page.getByRole("button", { name: "Region brief", exact: true }).click();
  await expect(page.locator(".hud-popover h2")).toContainText("Congo");
  await page.getByRole("heading", { name: "Global disease monitor" }).click();
  await page
    .getByRole("button", { name: "Source connectivity", exact: true })
    .click();
  const sources = page.getByRole("dialog", {
    name: "Source connectivity",
    exact: true,
  });
  await expect(sources.locator(".source-status-list article")).toHaveCount(5);
  await expect(
    sources.locator("article").filter({ hasText: "Korea Disease Control" }),
  ).toContainText("Unavailable");
});
