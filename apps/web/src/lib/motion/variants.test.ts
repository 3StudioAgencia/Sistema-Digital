import { describe, expect, it } from "vitest";

import { DURATION, REVEAL_OFFSET, STAGGER } from "./tokens";
import { fadeRise, staggerContainer } from "./variants";

type ShowShape = {
  opacity: number;
  y: number;
  x: number;
  scale: number;
  transition: { duration: number; ease: number[] };
};
type ContainerShape = {
  transition: { staggerChildren: number; delayChildren: number };
};

describe("fadeRise (variant de reveal)", () => {
  it("com movimento normal usa deslocamento e duração padrão (tokens)", () => {
    const v = fadeRise(false);
    expect(v.hidden).toEqual({ opacity: 0, y: REVEAL_OFFSET.y, x: 0, scale: 1 });
    const show = v.show as unknown as ShowShape;
    expect(show).toMatchObject({ opacity: 1, y: 0, x: 0, scale: 1 });
    expect(show.transition.duration).toBe(DURATION.short);
  });

  it("duração de reveal fica dentro da faixa (≤ 300 ms)", () => {
    const show = fadeRise(false).show as unknown as ShowShape;
    expect(show.transition.duration).toBeLessThanOrEqual(0.3);
  });

  it("respeita overrides (dx/scale/duration) com movimento normal", () => {
    const v = fadeRise(false, { dy: 0, dx: REVEAL_OFFSET.x, scale: 0.98, duration: DURATION.micro });
    expect(v.hidden).toEqual({ opacity: 0, y: 0, x: REVEAL_OFFSET.x, scale: 0.98 });
    const show = v.show as unknown as ShowShape;
    expect(show.transition.duration).toBe(DURATION.micro);
  });

  it("sob reduced-motion zera deslocamento, escala e duração (instantâneo)", () => {
    const v = fadeRise(true, { dy: 40, dx: 40, scale: 0.5, duration: DURATION.long });
    expect(v.hidden).toEqual({ opacity: 0, y: 0, x: 0, scale: 1 });
    const show = v.show as unknown as ShowShape;
    expect(show.transition.duration).toBe(DURATION.instant);
  });
});

describe("staggerContainer (cascata)", () => {
  it("com movimento normal escalona filhos pelo gap dos tokens", () => {
    const v = staggerContainer(false);
    const show = v.show as unknown as ContainerShape;
    expect(show.transition.staggerChildren).toBe(STAGGER.gap);
    expect(show.transition.delayChildren).toBe(STAGGER.delayInicial);
  });

  it("sob reduced-motion zera o gap e o atraso (todos surgem juntos)", () => {
    const v = staggerContainer(true, { gap: 0.2, delayInicial: 0.3 });
    const show = v.show as unknown as ContainerShape;
    expect(show.transition.staggerChildren).toBe(0);
    expect(show.transition.delayChildren).toBe(0);
  });
});
