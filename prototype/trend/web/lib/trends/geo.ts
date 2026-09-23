/* 지구·지도에 공통으로 쓰는 지리 데이터. world-atlas 110m 국경 + 나라별 대표 좌표. */
import { geoCentroid } from "d3-geo";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";

type Topo = Topology<{ countries: GeometryCollection<{ name: string }> }>;
export type CountryFeature = GeoJSON.Feature<GeoJSON.Geometry, { name: string }> & { id?: string | number };

const topo = world as unknown as Topo;
export const FEATURES = feature(topo, topo.objects.countries).features as CountryFeature[];

// world-atlas 는 ISO 3166-1 숫자 id → alpha-2
export const ISO: Record<string, string> = {
  "410": "KR", "392": "JP", "360": "ID", "764": "TH", "704": "VN", "158": "TW", "356": "IN", "036": "AU", "840": "US", "826": "GB",
  "276": "DE", "076": "BR", "484": "MX", "608": "PH", "702": "SG", "250": "FR", "724": "ES", "792": "TR", "566": "NG", "710": "ZA",
  "032": "AR", "124": "CA", "818": "EG", "682": "SA", "458": "MY", "156": "CN", "784": "AE",
};
export const codeOf = (f: CountryFeature) => ISO[String(f.id)];

// 중심점은 기하 중심이 어긋나는 나라(알래스카가 딸린 미국 등)만 손으로 잡는다
const OVERRIDE: Record<string, [number, number]> = {
  US: [39.5, -98.4], KR: [36.5, 127.8], JP: [36.2, 138.3], GB: [54.0, -2.0], IN: [22.0, 79.0], BR: [-10.0, -52.0], AU: [-25.0, 134.0],
  ID: [-2.5, 118.0], CN: [35.0, 104.0], AE: [24.0, 54.0], TH: [15.0, 101.0], VN: [16.0, 107.0], TW: [23.7, 121.0], PH: [12.9, 122.0],
  MX: [23.6, -102.5], DE: [51.2, 10.4],
};
export const CENTROID: Record<string, { lat: number; lng: number }> = {};
for (const f of FEATURES) {
  const code = codeOf(f);
  if (!code) continue;
  const o = OVERRIDE[code];
  if (o) CENTROID[code] = { lat: o[0], lng: o[1] };
  else {
    const [lng, lat] = geoCentroid(f as never);
    CENTROID[code] = { lat, lng };
  }
}
