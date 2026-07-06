/** Fixed, decorative ambient glow — two large soft blurred blobs behind all content.
 * Static (no motion) so it costs nothing and needs no reduced-motion handling; purely
 * atmospheric, never carries information (aria-hidden, pointer-events-none). */
export default function AmbientBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
      <div className="absolute -top-40 -right-32 w-[36rem] h-[36rem] rounded-full bg-accent/10 blur-3xl" />
      <div className="absolute top-1/3 -left-40 w-[30rem] h-[30rem] rounded-full bg-info/8 blur-3xl" />
      <div className="absolute bottom-0 right-1/4 w-[24rem] h-[24rem] rounded-full bg-good/6 blur-3xl" />
    </div>
  );
}
