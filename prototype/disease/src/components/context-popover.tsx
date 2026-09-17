"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";

export default function ContextPopover({
  label,
  icon,
  children,
}: {
  label: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) {
        setOpen(false);
        setPinned(false);
      }
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        setPinned(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <div
      className="hud-tool"
      ref={root}
      onPointerEnter={(event) => {
        clearTimeout(timer.current);
        if (event.pointerType === "mouse") setOpen(true);
      }}
      onPointerLeave={() => {
        if (!pinned) timer.current = setTimeout(() => setOpen(false), 180);
      }}
    >
      <button
        ref={trigger}
        className={`hud-trigger ${open ? "active" : ""}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          const next = !pinned;
          setPinned(next);
          setOpen(next);
        }}
      >
        {icon}
        <span>{label}</span>
      </button>
      {open ? (
        <section id={id} className="hud-popover" aria-label={label}>
          <div className="hud-popover-title">
            <strong>{label}</strong>
            <button
              className="icon-button"
              aria-label={`Close ${label}`}
              onClick={() => {
                setOpen(false);
                setPinned(false);
              }}
            >
              {<X size={15} />}
            </button>
          </div>
          {children}
        </section>
      ) : null}
    </div>
  );
}
