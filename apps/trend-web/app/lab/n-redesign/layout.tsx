import type { Metadata } from "next";
import { Frame } from "@/components/lab/n-redesign/frame";
import "./n-redesign.css";

/* 시안 n-redesign — 앱의 틀 대신 이 시안이 제 틀을 그린다. 문서: docs/디자인-시안/n-redesign.md */
export const metadata: Metadata = { title: { default: "Trend Interpreter", template: "%s | Trend Interpreter" } };

export default function NRedesignLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="lab-n-redesign">
      <Frame>{children}</Frame>
    </div>
  );
}
