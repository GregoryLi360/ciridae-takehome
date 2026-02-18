import { useEffect, useRef } from "react";

/**
 * Full-screen aurora/wave background effect rendered on a <canvas>.
 * Uses layered sine waves with slow-drifting hue to create flowing
 * colored bands on a dark background, similar to Ciridae's site.
 */
export default function Aurora() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width: number;
    let height: number;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.scale(dpr, dpr);
    }

    resize();
    window.addEventListener("resize", resize);

    const bands = [
      { yOff: 0.30, amp: 80, freq: 0.0015, speed: 0.0004, hueBase: 260, sat: 70, alpha: 0.12 },
      { yOff: 0.42, amp: 60, freq: 0.002,  speed: 0.0003, hueBase: 200, sat: 80, alpha: 0.10 },
      { yOff: 0.55, amp: 90, freq: 0.001,  speed: 0.0005, hueBase: 310, sat: 60, alpha: 0.08 },
      { yOff: 0.35, amp: 50, freq: 0.0025, speed: 0.0002, hueBase: 170, sat: 75, alpha: 0.07 },
      { yOff: 0.50, amp: 70, freq: 0.0018, speed: 0.00035, hueBase: 40, sat: 65, alpha: 0.06 },
    ];

    function draw(t: number) {
      ctx!.clearRect(0, 0, width, height);

      for (const b of bands) {
        const hue = (b.hueBase + t * 0.008) % 360;
        const baseY = height * b.yOff;

        ctx!.beginPath();
        ctx!.moveTo(0, height);

        for (let x = 0; x <= width; x += 3) {
          const y =
            baseY +
            Math.sin(x * b.freq + t * b.speed) * b.amp +
            Math.sin(x * b.freq * 0.5 + t * b.speed * 1.3) * b.amp * 0.5;
          ctx!.lineTo(x, y);
        }

        ctx!.lineTo(width, height);
        ctx!.closePath();

        const grad = ctx!.createLinearGradient(0, baseY - b.amp, 0, baseY + b.amp * 2);
        grad.addColorStop(0, `hsla(${hue}, ${b.sat}%, 60%, 0)`);
        grad.addColorStop(0.3, `hsla(${hue}, ${b.sat}%, 60%, ${b.alpha})`);
        grad.addColorStop(0.7, `hsla(${hue}, ${b.sat}%, 50%, ${b.alpha * 0.6})`);
        grad.addColorStop(1, `hsla(${hue}, ${b.sat}%, 40%, 0)`);

        ctx!.fillStyle = grad;
        ctx!.fill();
      }

      animId = requestAnimationFrame(draw);
    }

    animId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0 pointer-events-none"
      aria-hidden="true"
    />
  );
}
