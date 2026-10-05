import { permanentRedirect } from "next/navigation";

/* 예전 주소(10-06 하루 공개) — 설명은 '/about' 으로 합쳤다. 단계별 모델 기록은 관리 화면(/admin/status)에 있다. */
export default function GemmaRedirect() {
  permanentRedirect("/about");
}
