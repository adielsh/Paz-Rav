import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { IconInfo, IconX } from "./Icon";

/** Accessible modal: scrim (dismiss on click/Escape), focus the panel on open, spring-in
 * animation, RTL body. Rendered through a PORTAL to document.body — a `position: fixed`
 * element inside a transformed ancestor (e.g. a card with a hover translate) is positioned
 * relative to that ancestor, not the viewport, which traps and clips the modal inside the
 * card. The portal escapes the card's DOM entirely. */
export function Modal({
  open,
  onClose,
  title,
  icon,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  // Keep the latest onClose in a ref so the open-effect depends ONLY on `open` — an inline
  // `onClose` prop is a new function every parent render (and scans re-render the list every
  // few seconds), which used to re-run the effect: re-focusing the panel and re-locking the
  // body over and over — the "stuck and flickering" bug.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // don't scroll the page behind the modal
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      // never let clicks/keys bubble into whatever the trigger was nested in (cards etc.)
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
    >
      {/* scrim: strong enough (≈55%) to isolate the foreground */}
      <div
        className="absolute inset-0 bg-[rgb(2_10_9_/_0.55)] backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        dir="rtl"
        className="animate-modal relative w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl border border-line bg-panel shadow-elevated outline-none"
      >
        <div className="sticky top-0 flex items-center gap-2.5 px-5 py-3.5 border-b border-line bg-panel/95 backdrop-blur">
          {icon && <span className="text-primary">{icon}</span>}
          <h3 className="font-bold text-[15px] text-ink flex-1">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="סגור"
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-ink-2 hover:text-ink hover:bg-panel2"
          >
            <IconX width={17} height={17} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

/** A small round info button that opens a Modal with detail — the progressive-disclosure
 * affordance used across cards so the surface stays clean until the user asks for more. */
export function InfoButton({
  title,
  icon,
  label = "מידע נוסף",
  children,
}: {
  title: string;
  icon?: ReactNode;
  label?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation(); // don't select/activate the card the button sits on
          setOpen(true);
        }}
        aria-label={label}
        title={label}
        className="inline-flex items-center justify-center w-7 h-7 rounded-full border border-line text-ink-3 hover:text-primary hover:border-primary/50 hover:bg-primary/5"
      >
        <IconInfo width={15} height={15} />
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={title} icon={icon}>
        {children}
      </Modal>
    </>
  );
}
