-- rate_limit_contadores_self.sql — o ator so toca a propria linha (W3-C10)
--
-- FOR ALL: USING escopa SELECT/UPDATE (e o RETURNING do upsert) a linha do ator;
-- WITH CHECK barra INSERT/UPDATE com user_id de outro. O limitador ja insere com
-- public.app_current_user_id(), entao a policy e defesa em profundidade: um ator
-- nunca enxerga nem incrementa o contador de outro (anti-abuso sem virar canal
-- lateral de enumeracao).
--
-- Idempotente. Reaplicar apos qualquer DROP/recriacao da tabela (CLAUDE.md §9).
DROP POLICY IF EXISTS rate_limit_contadores_self ON rate_limit_contadores;
CREATE POLICY rate_limit_contadores_self ON rate_limit_contadores FOR ALL
    TO authenticated
    USING (user_id = public.app_current_user_id())
    WITH CHECK (user_id = public.app_current_user_id());
