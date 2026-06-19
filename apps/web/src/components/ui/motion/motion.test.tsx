import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setReducedMotion } from "@/test/motion";

import { PageTransition, Reveal, Stagger, StaggerItem } from "./index";

afterEach(() => {
  setReducedMotion(false);
});

describe("Primitivas de animação (W6-C19)", () => {
  it("<PageTransition> renderiza o conteúdo (movimento normal)", () => {
    setReducedMotion(false);
    render(<PageTransition>conteúdo da página</PageTransition>);
    expect(screen.getByText("conteúdo da página")).toBeInTheDocument();
  });

  it("<PageTransition> renderiza o conteúdo sob reduced-motion (instantâneo)", () => {
    setReducedMotion(true);
    render(<PageTransition>conteúdo reduzido</PageTransition>);
    expect(screen.getByText("conteúdo reduzido")).toBeInTheDocument();
  });

  it("<Reveal> renderiza o filho em ambos os modos", () => {
    setReducedMotion(false);
    const { unmount } = render(<Reveal>um elemento</Reveal>);
    expect(screen.getByText("um elemento")).toBeInTheDocument();
    unmount();
    setReducedMotion(true);
    render(<Reveal>um elemento</Reveal>);
    expect(screen.getByText("um elemento")).toBeInTheDocument();
  });

  it("<Stagger>/<StaggerItem> revela todos os itens (movimento normal)", () => {
    setReducedMotion(false);
    render(
      <Stagger>
        <StaggerItem>item A</StaggerItem>
        <StaggerItem>item B</StaggerItem>
        <StaggerItem>item C</StaggerItem>
      </Stagger>,
    );
    expect(screen.getByText("item A")).toBeInTheDocument();
    expect(screen.getByText("item B")).toBeInTheDocument();
    expect(screen.getByText("item C")).toBeInTheDocument();
  });

  it("<Stagger>/<StaggerItem> revela todos os itens sob reduced-motion", () => {
    setReducedMotion(true);
    render(
      <Stagger>
        <StaggerItem>item X</StaggerItem>
        <StaggerItem>item Y</StaggerItem>
      </Stagger>,
    );
    expect(screen.getByText("item X")).toBeInTheDocument();
    expect(screen.getByText("item Y")).toBeInTheDocument();
  });
});
