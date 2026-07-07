import { useEffect, useRef } from "react";

/** Fixed, decorative ambient layer — large soft blurred orbs that slowly drift (CSS) and
 * shift a touch with scroll (a subtle parallax). Purely atmospheric: aria-hidden,
 * pointer-events-none, and it respects prefers-reduced-motion (drift + parallax both stop).
 */
export default function AmbientBackground() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !ref.current) return;
    const el = ref.current;
    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        // move the orb layer a fraction of the scroll for depth, without stealing the scroll
        el.style.transform = `translateY(${window.scrollY * 0.12}px)`;
        raf = 0;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={ref} className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
      <div className="orb-a absolute -top-40 -right-32 w-[38rem] h-[38rem] rounded-full bg-primary/15 blur-3xl" />
      <div className="orb-b absolute top-1/4 -left-44 w-[32rem] h-[32rem] rounded-full bg-accent/12 blur-3xl" />
      <div className="orb-c absolute bottom-0 right-1/4 w-[26rem] h-[26rem] rounded-full bg-info/10 blur-3xl" />
      {/* very faint grid for texture/depth (barely visible, adds a premium feel) */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgb(var(--ink)) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--ink)) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />
    </div>
  );
}
