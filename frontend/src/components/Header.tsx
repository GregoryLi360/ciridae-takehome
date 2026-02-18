export default function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="max-w-[1600px] mx-auto px-8 h-[72px] flex items-center justify-between">
        <a
          href="/"
          className="font-mono font-semibold text-lg tracking-[-0.02em] uppercase"
        >
          Ciridae
        </a>
        <span className="font-mono text-xs tracking-[0.08em] uppercase text-muted-foreground">
          Insurance Rebuttal
        </span>
      </div>
    </header>
  );
}
