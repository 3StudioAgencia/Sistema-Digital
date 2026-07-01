
import { Reveal } from "@/components/ui/motion";

import styles from "./placeholder.module.css";

type PlaceholderProps = {
  titulo: string;
  componente?: string;
};

export function Placeholder({ titulo, componente }: PlaceholderProps) {
  return (
    <section className={styles.wrap}>
      <Reveal>
        <h1 className={styles.titulo}>{titulo}</h1>
        <p className={styles.texto}>
          Esta área está em construção
          {componente ? ` — chega com o componente ${componente} do roadmap.` : "."}
        </p>
      </Reveal>
    </section>
  );
}
