import { readFile, writeFile } from "node:fs/promises";
import { feature } from "topojson-client";
import countries from "world-countries";
import type { Topology, GeometryCollection } from "topojson-specification";

async function main() {
  const topology = JSON.parse(
    await readFile("node_modules/world-atlas/countries-110m.json", "utf8"),
  ) as Topology<{ countries: GeometryCollection }>;
  const collection = feature(topology, topology.objects.countries);
  const result = {
    type: "FeatureCollection",
    features: collection.features.map((feature) => {
      const country = countries.find(
        (item) => item.ccn3 === String(feature.id),
      );
      return {
        ...feature,
        properties: {
          name: (feature.properties as { name: string }).name,
          code: country?.cca2 ?? String(feature.id),
          latitude: country?.latlng[0] ?? 0,
          longitude: country?.latlng[1] ?? 0,
        },
      };
    }),
  };
  await writeFile("src/data/countries.geo.json", JSON.stringify(result));
  await writeFile(
    "src/data/country-index.json",
    JSON.stringify(
      result.features
        .map((feature) => feature.properties)
        .filter((country) => country.code.length === 2 && country.code !== "AQ")
        .sort((a, b) => a.name.localeCompare(b.name)),
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
