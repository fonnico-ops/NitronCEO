-- KPI: manutencao_molde
-- Pergunta: quanto de produção o molde está tirando da fábrica?
--
-- Este é o primeiro KPI de Projetos/Moldes. Antes dele o papel existia no
-- cadastro e não tinha o que cobrar, porque a parada de molde não era
-- medida em lugar nenhum vivo.
--
-- FONTE: TPRIWC + TPRMTP, motivo {{MOTIVO_MOLDE}} ("MANUTENÇÃO DE MOLDE",
-- MOTIVOPARADA='C' = corretiva). Nos últimos 30 dias: 69 paradas somando
-- 46.397 minutos — 773 HORAS de injetora parada por molde, média de 672 min
-- por parada.
--
-- Comparação que dá a dimensão, no mesmo período:
--   Manutenção de molde    69 paradas   46.397 min
--   Manutenção de máquina  74 paradas   61.849 min   (é da manutenção, não de projetos)
--   Setup                 218 paradas   71.527 min
--
-- A métrica é HORAS_PARADAS, não a contagem: uma parada de molde de 11 horas
-- e cinco de 20 minutos não são o mesmo problema, e contar paradas trata as
-- duas igual.
--
-- Params: {{MOTIVO_MOLDE}}  {{JANELA_DIAS}}

WITH PARADA AS (
  SELECT I.CODWCP, I.AD_IDIPROC,
         (NVL(I.DHFINAL, SYSDATE) - I.DHINCIAL) * 1440 AS MINUTOS,
         CASE WHEN I.DHFINAL IS NULL THEN 1 ELSE 0 END AS ABERTA
    FROM TPRIWC I /*CC TPRIWC CC*/
   WHERE I.AD_CODMTP = {{MOTIVO_MOLDE}}
     AND I.DHINCIAL >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
),
AGG AS (
  SELECT COUNT(*) AS PARADAS,
         SUM(ABERTA) AS ABERTAS_AGORA,
         ROUND(NVL(SUM(MINUTOS),0)/60, 1) AS HORAS_PARADAS,
         ROUND(NVL(AVG(MINUTOS),0), 1) AS MEDIA_MIN,
         COUNT(DISTINCT CODWCP) AS MAQUINAS_AFETADAS
    FROM PARADA
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.HORAS DESC) AS LISTA
    FROM (SELECT ROUND(SUM(P.MINUTOS)/60,1) AS HORAS,
                 W.NOME || ': ' || ROUND(SUM(P.MINUTOS)/60,1) || 'h em '
                   || COUNT(*) || ' paradas' AS TXT
            FROM PARADA P JOIN TPRWCP W ON W.CODWCP = P.CODWCP
           GROUP BY W.NOME
           ORDER BY SUM(P.MINUTOS) DESC FETCH FIRST 8 ROWS ONLY) X
)
SELECT A.PARADAS, A.ABERTAS_AGORA, A.HORAS_PARADAS, A.MEDIA_MIN,
       A.MAQUINAS_AFETADAS, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
