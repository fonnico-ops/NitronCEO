-- KPI: maquinas_paradas
-- Pergunta: quantas injetoras estão paradas agora, e POR QUÊ?
--
-- FONTE: TPRIWC — parada em aberto é DHFINAL IS NULL, com o motivo em
-- TPRMTP. Isto substitui o proxy anterior (tempo desde TPRWCP.AD_DHCICLO),
-- que dizia QUE parou mas não dizia por quê. A pergunta da cobrança sempre
-- foi o motivo; agora o dado responde.
--
-- REFEIÇÃO NÃO É PROBLEMA. Motivo {{MOTIVO_REFEICAO}} é parada programada:
-- em 22/09/2026 às 18:30, 8 das 13 paradas abertas eram refeição, e contá-las
-- dispararia alerta todo dia no mesmo horário. Elas saem do número principal
-- e entram em REFEICAO_LONGA quando passam de {{REFEICAO_TETO_MIN}} minutos —
-- aí não é refeição, é apontamento que ninguém fechou.
--
-- APURADO EM 22/09/2026 18:30 — 13 paradas abertas:
--   INJETORA 15  MANUTENÇÃO DE MOLDE  139 min
--   INJETORA 38  SETUP                 32 min
--   INJETORA 35  (SEM MOTIVO)          81 min
--   INJETORA 29  (SEM MOTIVO)          61 min
--   +8 em REFEIÇÃO, a mais antiga há 128 min
--
-- Params: {{MIN_PARADA_ALERTA}}  {{MOTIVO_REFEICAO}}  {{REFEICAO_TETO_MIN}}

WITH ABERTA AS (
  SELECT I.CODWCP, I.AD_CODMTP, I.DHINCIAL,
         ROUND((SYSDATE - I.DHINCIAL) * 1440) AS MINUTOS,
         NVL(M.DESCRICAO, '(SEM MOTIVO)') AS MOTIVO
    FROM TPRIWC I /*CC TPRIWC CC*/
    LEFT JOIN TPRMTP M ON M.CODMTP = I.AD_CODMTP
   WHERE I.DHFINAL IS NULL
),
NAO_PROGRAMADA AS (
  SELECT * FROM ABERTA
   WHERE NVL(AD_CODMTP,0) <> {{MOTIVO_REFEICAO}}
),
CONTEXTO AS (
  -- Escalares em CTE própria: o Oracle recusa subquery escalar ao lado de
  -- função de grupo no mesmo SELECT sem GROUP BY.
  SELECT
    (SELECT COUNT(*) FROM TPRWCP WHERE NVL(AD_MONITORADO,'N') = 'S') AS MONITORADAS,
    (SELECT COUNT(*) FROM ABERTA)                                    AS PARADAS_ABERTAS,
    (SELECT COUNT(*) FROM ABERTA
      WHERE NVL(AD_CODMTP,0) = {{MOTIVO_REFEICAO}}
        AND MINUTOS > {{REFEICAO_TETO_MIN}})                         AS REFEICAO_LONGA
  FROM DUAL
),
AGG AS (
  SELECT
    COUNT(*)                                                         AS NAO_PROGRAMADAS,
    SUM(CASE WHEN MINUTOS > {{MIN_PARADA_ALERTA}} THEN 1 ELSE 0 END) AS PARADAS_60MIN,
    SUM(CASE WHEN MOTIVO = '(SEM MOTIVO)' THEN 1 ELSE 0 END)         AS SEM_MOTIVO
  FROM NAO_PROGRAMADA
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.MINUTOS DESC) AS LISTA
    FROM (SELECT N.MINUTOS,
                 W.NOME || ': ' || N.MOTIVO || ' há ' || N.MINUTOS || ' min' AS TXT
            FROM NAO_PROGRAMADA N JOIN TPRWCP W ON W.CODWCP = N.CODWCP
           ORDER BY N.MINUTOS DESC FETCH FIRST 12 ROWS ONLY) X
)
SELECT C.MONITORADAS, C.PARADAS_ABERTAS, A.NAO_PROGRAMADAS, A.PARADAS_60MIN,
       A.SEM_MOTIVO, C.REFEICAO_LONGA, T.LISTA
  FROM AGG A CROSS JOIN CONTEXTO C CROSS JOIN TOPO T
