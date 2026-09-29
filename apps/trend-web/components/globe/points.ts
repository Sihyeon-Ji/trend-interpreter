/* 지도에 올리는 나라 좌표 — world-atlas 110m 도형의 중심에, 도형이 없는 목표 지역을 더한다.
   110m 지도에는 홍콩(344)과 싱가포르(702)의 도형이 아예 없어서 말풍선·클릭이 사라졌다(개편 검토). 이 둘은 점과 말풍선으로 그린다. */
import { CENTROID as SHAPES } from "@/lib/trends/geo";

export const POINT_ONLY: Record<string, { lat: number; lng: number }> = {
  HK: { lat: 22.32, lng: 114.17 },
  SG: { lat: 1.35, lng: 103.82 },
};

export const CENTROID: Record<string, { lat: number; lng: number }> = { ...SHAPES, ...POINT_ONLY };
