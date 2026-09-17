import { expect, test } from "@playwright/test";

test("report workspace preserves bookmarks, citations, and evidence export", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Reports & analysis" }),
  ).toBeVisible();
  const firstTitle = await page
    .locator(".archive-report-main>strong")
    .first()
    .innerText();
  await page
    .getByRole("button", {
      name: `Add to watchlist: ${firstTitle}`,
      exact: true,
    })
    .click();
  await page.getByRole("button", { name: "Saved (1)", exact: true }).click();
  await expect(page.locator(".archive-report")).toHaveCount(1);
  await page.reload();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await page.getByRole("button", { name: "Saved (1)", exact: true }).click();
  await expect(page.locator(".archive-report")).toHaveCount(1);
  await page.locator(".archive-report-main").first().click();
  const detail = page.getByRole("dialog", {
    name: "Official report",
    exact: true,
  });
  await expect(
    detail.getByRole("link", { name: "Read official report" }),
  ).toHaveAttribute("href", /^https:\/\//);
  await detail.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "Generate report", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your official-source evidence brief" }),
  ).toBeVisible();
  await expect(page.locator(".report-composer")).toContainText(
    "Gemini analysis is not configured",
  );
  await expect(page.locator(".report-composer")).toContainText(
    "No scenarios generated",
  );
  await page.locator(".citation").first().click();
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "Close dialog" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export brief" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.md$/);
  const dataDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export filtered reports" }).click();
  expect((await dataDownload).suggestedFilename()).toBe(
    "outbreak-atlas-reports.json",
  );
  await page.screenshot({
    path: "artifacts/reports-desktop.png",
    fullPage: true,
  });
});
