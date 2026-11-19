import confetti from "canvas-confetti";

const KEY = "jaa.milestones";

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function celebrate(force = false) {
  if (reducedMotion() && !force) return;
  const colors = ["#cfa636", "#f4e9c9", "#e3c46b", "#ffffff", "#9d7a18"];
  confetti({ particleCount: 90, spread: 70, startVelocity: 38, origin: { y: 0.65 }, colors, scalar: 0.9 });
  setTimeout(() => confetti({ particleCount: 40, spread: 100, origin: { y: 0.6 }, colors, scalar: 0.7 }), 180);
}

/** Fire confetti once per milestone (first category, first designs, first sale, first insights, first plan). */
export function milestone(name: string) {
  try {
    const done = JSON.parse(localStorage.getItem(KEY) || "{}");
    if (done[name]) return;
    done[name] = Date.now();
    localStorage.setItem(KEY, JSON.stringify(done));
  } catch {
    /* storage blocked: still celebrate */
  }
  celebrate();
}
