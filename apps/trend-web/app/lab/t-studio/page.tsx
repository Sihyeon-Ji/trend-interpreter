import type { Metadata } from "next";
import { PrototypeFrame } from "@/components/lab/t-studio/prototype-frame";

/* 디자인 초안 5 '마케터 스튜디오형' — 팀원 화면 기획 초안을 데모 영상 순서에 맞춰 다듬은 것. 문서: docs/디자인-시안/t-studio.md */
export const metadata: Metadata = { title: "초안 5 · 마케터 스튜디오형 · 트렌드 통역" };

export default function TStudioPage() {
  return <PrototypeFrame src="/lab/t-studio/proto" title="초안 5 마케터 스튜디오형 화면" />;
}
