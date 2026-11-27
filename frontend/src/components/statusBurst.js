import { useMemo } from "react";

const COLORS = ["#0f6e62", "#e2b15a", "#d4654a", "#1c1915", "#7eb8ae", "#f3d7a1"];

export function effectFor(status) {
  if (status === "in_process") return "plane";
  if (status === "interview" || status === "offered") return "confetti";
  return null;
}

function Confetti() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 72 }, (_, index) => ({
        id: index,
        left: Math.random() * 100,
        delay: Math.random() * 0.35,
        duration: 1.5 + Math.random() * 1.1,
        color: COLORS[index % COLORS.length],
        spin: 160 + Math.random() * 420,
        size: 7 + (index % 5),
        drift: -40 + Math.random() * 80,
      })),
    []
  );

  return (
    <div className="burst confetti" aria-hidden="true">
      {pieces.map((piece) => (
        <span
          key={piece.id}
          style={{
            left: `${piece.left}%`,
            width: piece.size,
            height: piece.size * 0.55,
            background: piece.color,
            animationDelay: `${piece.delay}s`,
            animationDuration: `${piece.duration}s`,
            "--spin": `${piece.spin}deg`,
            "--drift": `${piece.drift}px`,
          }}
        />
      ))}
    </div>
  );
}

function PaperPlane() {
  return (
    <div className="burst plane" aria-hidden="true">
      <div className="plane-shot">
        <span className="plane-streaks" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <svg className="plane-icon" viewBox="0 0 92 40" width="118" height="52">
          <path d="M2 20 L88 3 L50 20 L88 20 L42 37 L32 20 Z" fill="#0f6e62" />
          <path d="M2 20 L88 3 L50 20 Z" fill="#14897a" />
          <path d="M8 20 L50 20" fill="none" stroke="#d8f3ee" strokeWidth="1.6" />
        </svg>
      </div>
    </div>
  );
}

function StatusBurst({ kind }) {
  if (kind === "confetti") return <Confetti />;
  if (kind === "plane") return <PaperPlane />;
  return null;
}

export default StatusBurst;
