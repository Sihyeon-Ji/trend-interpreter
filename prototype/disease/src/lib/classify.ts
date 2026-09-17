import countries from "world-countries";
import type { Country, Report } from "./types";

const diseasePatterns: [string, RegExp][] = [
  ["Ebola", /ebola|bundibugyo|에볼라/i],
  ["Avian influenza", /avian|bird flu|h5n\d|h7n\d|조류인플루엔자/i],
  ["Mpox", /mpox|monkeypox|엠폭스/i],
  ["Cholera", /cholera|콜레라/i],
  ["Dengue", /dengue|뎅기/i],
  ["Measles", /measles|홍역/i],
  ["COVID-19", /covid|sars-cov-2|코로나/i],
  ["Chikungunya", /chikungunya|치쿤구니야/i],
  ["Hantavirus", /hantavirus|한타바이러스/i],
  ["Marburg", /marburg|마버그/i],
  ["MERS", /\bmers\b|메르스/i],
  ["Polio", /polio|poliomyelitis|폴리오/i],
  ["Yellow fever", /yellow fever|황열/i],
  ["West Nile", /west nile/i],
  ["Meningitis", /meningitis|meningococcal/i],
  ["Salmonella", /salmonella/i],
  ["Influenza", /influenza|\bflu\b|인플루엔자/i],
  ["Nipah", /nipah|니파/i],
  ["Pertussis", /pertussis|whooping cough|백일해/i],
  ["Rift Valley fever", /rift valley/i],
  ["Oropouche", /oropouche/i],
  ["Lassa fever", /lassa/i],
];

export function detectDiseases(text: string): string[] {
  const found = diseasePatterns
    .filter(([, pattern]) => pattern.test(text))
    .map(([name]) => name);
  return found.includes("Avian influenza")
    ? found.filter((name) => name !== "Influenza")
    : found;
}

const aliases: Record<string, string[]> = {
  CD: [
    "Democratic Republic of the Congo",
    "Democratic Republic of Congo",
    "DR Congo",
    "DRC",
  ],
  CG: ["Republic of the Congo", "Republic of Congo"],
  US: ["United States", "United States of America", "USA"],
  GB: ["United Kingdom", "England", "Scotland", "Wales", "Northern Ireland"],
  KR: ["Republic of Korea", "South Korea", "대한민국"],
  KP: ["Democratic People's Republic of Korea", "North Korea"],
  TZ: ["Tanzania", "United Republic of Tanzania"],
};

const countryNames = countries
  .flatMap((country) => {
    const names = aliases[country.cca2] ?? [
      country.name.common,
      country.name.official,
    ];
    const value: Country = {
      code: country.cca2,
      name: country.name.common,
      latitude: country.latlng[0],
      longitude: country.latlng[1],
    };
    return [...new Set(names)]
      .filter((name) => name.length >= 3)
      .map((name) => ({ name, value }));
  })
  .sort((a, b) => b.name.length - a.name.length);

export function detectCountries(title: string): Country[] {
  let remaining = title;
  const found = new Map<string, Country>();
  for (const { name, value } of countryNames) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`(?<![\\p{L}])${escaped}(?![\\p{L}])`, "giu");
    if (!pattern.test(remaining)) continue;
    found.set(value.code, value);
    remaining = remaining.replace(pattern, " ");
  }
  return [...found.values()];
}

export function detectTopics(text: string): string[] {
  const topics: string[] = [];
  if (/cross.border|international spread|imported case/i.test(text))
    topics.push("Cross-border context");
  if (/avian|zoonot|poultry|animal.to.human/i.test(text))
    topics.push("Human–animal interface");
  if (/vaccin|preparedness|surveillance/i.test(text))
    topics.push("Response & preparedness");
  if (/new variant|novel virus|unknown (?:origin|cause)/i.test(text))
    topics.push("Novelty mention");
  return topics.length ? topics : ["Situation update"];
}

export function enrichReport(
  report: Omit<Report, "diseases" | "countries" | "topics">,
): Report {
  const text = `${report.title} ${report.summary}`;
  return {
    ...report,
    diseases: detectDiseases(text),
    countries: detectCountries(report.title),
    topics: detectTopics(text),
  };
}
