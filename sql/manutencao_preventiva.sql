-- KPI: manutencao_preventiva
-- Pergunta: a manutenção está prevenindo ou apagando incêndio?
--
-- AD_TGFMANUT.TIPOMANUT separa CORRETIVA de PREVENTIVA. A proporção entre as
-- duas é o indicador mais direto de maturidade de manutenção que existe: ela
-- não depende de meta nem de benchmark externo, só da própria operação.
--
-- APURADO EM 22/09/2026 — base histórica completa (12.310 OS):
--   CORRETIVA   11.090  (90,1%)
--   PREVENTIVA   1.220  ( 9,9%)
--
-- Nove em cada dez ordens de serviço são para consertar algo que já quebrou.
-- Isso conecta com dois outros KPIs desta matriz e explica parte deles:
--   manutencao_molde  — 773 horas de injetora parada por molde em 30 dias
--   ciclos_altos      — mediana em 128,5% do ciclo base
-- Máquina que só recebe atenção depois de quebrar roda mais devagar antes de
-- quebrar.
--
-- A métrica é o percentual de PREVENTIVA na janela, e o corte é por limite
-- INFERIOR: quanto menos preventiva, pior.
--
-- Params: {{JANELA_PREVENTIVA_DIAS}}

WITH OS AS (
  SELECT NVL(TIPOMANUT,'(sem classe)') AS TIPOMANUT, TIPO, DHOS
    FROM AD_TGFMANUT /*CC AD_TGFMANUT CC*/
   WHERE DHOS >= TRUNC(SYSDATE) - {{JANELA_PREVENTIVA_DIAS}}
),
AGG AS (
  SELECT COUNT(*) AS OS_JANELA,
         SUM(CASE WHEN TIPOMANUT = 'PREVENTIVA' THEN 1 ELSE 0 END) AS PREVENTIVAS,
         SUM(CASE WHEN TIPOMANUT = 'CORRETIVA' THEN 1 ELSE 0 END)  AS CORRETIVAS,
         ROUND(SUM(CASE WHEN TIPOMANUT = 'PREVENTIVA' THEN 1 ELSE 0 END)
               / NULLIF(COUNT(*),0) * 100, 1)                      AS PCT_PREVENTIVA
    FROM OS
),
POR_TIPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.N DESC) AS LISTA
    FROM (SELECT COUNT(*) AS N,
                 NVL(TIPO,'(sem tipo)') || ': '
                   || ROUND(SUM(CASE WHEN TIPOMANUT = 'PREVENTIVA' THEN 1 ELSE 0 END)
                            / NULLIF(COUNT(*),0) * 100)
                   || '% preventiva em ' || COUNT(*) || ' OS' AS TXT
            FROM OS GROUP BY NVL(TIPO,'(sem tipo)')) X
)
SELECT A.OS_JANELA, A.PREVENTIVAS, A.CORRETIVAS, A.PCT_PREVENTIVA, T.LISTA
  FROM AGG A CROSS JOIN POR_TIPO T
