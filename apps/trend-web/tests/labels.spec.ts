import { expect, test } from "@playwright/test";
import { nuanceChecked } from "../lib/labels";

test("only a human-reviewed meaning counts as having its nuance checked against sources", () => {
  expect(nuanceChecked({ verification: "verified_human" })).toBe(true);
  for (const verification of ["verified_auto", "unverified", "rejected", undefined]) {
    expect(nuanceChecked({ verification })).toBe(false);
  }
  expect(nuanceChecked(null)).toBe(false);
});
