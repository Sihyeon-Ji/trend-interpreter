import { describe, expect, it } from "vitest";
import { detectCountries, detectDiseases } from "../src/lib/classify";
import {
  parseFeed,
  parseWho,
  plainText,
  SOURCE_DEFINITIONS,
} from "../src/lib/sources";

describe("source normalization", () => {
  it("normalizes a WHO report with an explicit source URL and publication date", () => {
    const result = parseWho(
      JSON.stringify({
        value: [
          {
            Title: "Mpox – Uganda",
            PublicationDate: "2026-01-01T00:00:00Z",
            UrlName: "2026-DON001",
            Summary: "<p>Official &amp; verified</p>",
          },
        ],
      }),
    );
    expect(result).toHaveLength(1);
    expect(result[0].summary).toBe("Official & verified");
    expect(result[0].url).toBe(
      "https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON001",
    );
    expect(result[0].countries.map((c) => c.code)).toEqual(["UG"]);
  });
  it("does not fabricate a publication date for an invalid WHO entry", () => {
    expect(
      parseWho(
        JSON.stringify({
          value: [
            { Title: "Mpox", PublicationDate: "invalid", UrlName: "test" },
          ],
        }),
      ),
    ).toEqual([]);
  });
  it("rejects an unexpected WHO schema", () => {
    expect(() => parseWho('{"value":"not an array"}')).toThrow();
  });
  it("handles one RSS item without assuming an array", () => {
    const result = parseFeed(
      "<rss><channel><item><title>Dengue in Brazil</title><link>https://wwwnc.cdc.gov/travel/test</link><pubDate>Mon, 01 Jun 2026 00:00:00 GMT</pubDate><description><![CDATA[<p>Source summary</p>]]></description></item></channel></rss>",
      SOURCE_DEFINITIONS[1],
    );
    expect(result).toHaveLength(1);
    expect(result[0].diseases).toEqual(["Dengue"]);
    expect(result[0].summary).toBe("Source summary");
  });
  it("parses Atom alternate links and encoded summaries", () => {
    const result = parseFeed(
      '<feed><entry><title>Measles in England</title><updated>2026-01-01T00:00:00Z</updated><link rel="self" href="https://evil.test/a"/><link rel="alternate" href="https://www.gov.uk/government/news/measles"/><summary type="html">&lt;p&gt;Official report&lt;/p&gt;</summary></entry></feed>',
      SOURCE_DEFINITIONS[3],
    );
    expect(result[0].summary).toBe("Official report");
    expect(result[0].countries.map((c) => c.code)).toEqual(["GB"]);
  });
  it.each([
    "javascript:alert(1)",
    "https://evil.test/notices",
    "https://wwwnc.cdc.gov@evil.test/",
    "https://wwwnc.cdc.gov.evil.test/",
  ])("drops unsafe or non-official links: %s", (url) => {
    expect(
      parseFeed(
        `<rss><channel><item><title>Measles</title><pubDate>2026-01-01</pubDate><link>${url}</link></item></channel></rss>`,
        SOURCE_DEFINITIONS[1],
      ),
    ).toEqual([]);
  });
  it("marks the KDCA unsupported response as no usable data", () => {
    expect(
      parseFeed(
        "<rss><channel><item><title>This board unsupportable RSS function.</title><link/><pubDate/></item></channel></rss>",
        SOURCE_DEFINITIONS[4],
      ),
    ).toEqual([]);
  });
  it("rejects entity declarations and malformed XML", () => {
    expect(() =>
      parseFeed(
        '<!DOCTYPE rss [<!ENTITY a "x">]><rss/>',
        SOURCE_DEFINITIONS[1],
      ),
    ).toThrow();
    expect(() => parseFeed("<rss><channel>", SOURCE_DEFINITIONS[1])).toThrow();
  });
  it("removes scripts and styles and decodes entities into plain text", () => {
    expect(
      plainText(
        "<script>alert(1)</script><style>x</style><p>A &amp; B &#8211; C</p>",
      ),
    ).toBe("A & B – C");
  });
});

describe("disease and geography matching", () => {
  it("matches the longer Congo name without inventing a second country", () => {
    expect(
      detectCountries("Ebola - Democratic Republic of the Congo").map(
        (c) => c.code,
      ),
    ).toEqual(["CD"]);
  });
  it("does not map Crimean-Congo disease to a Congo country", () => {
    expect(
      detectCountries("Crimean-Congo haemorrhagic fever - Spain").map(
        (c) => c.code,
      ),
    ).toEqual(["ES"]);
  });
  it("does not match Niger inside Nigeria", () => {
    expect(detectCountries("Cholera - Nigeria").map((c) => c.code)).toEqual([
      "NG",
    ]);
  });
  it("does not assign a country to a global bulletin", () => {
    expect(detectCountries("Mpox – Global update")).toEqual([]);
  });
  it("distinguishes avian influenza from generic influenza", () => {
    expect(detectDiseases("Avian influenza A(H5N1)")).toEqual([
      "Avian influenza",
    ]);
  });
  it("supports multiple disease topics without implying separate cases", () => {
    expect(detectDiseases("Updates on dengue, mpox and cholera")).toEqual([
      "Mpox",
      "Cholera",
      "Dengue",
    ]);
  });
});
