-- KPI: maquinas_paradas
-- Pergunta: quantas das 45 injetoras estão sem tiro neste momento?
--
-- FONTE: batimento IoT gravado em TPRWCP.AD_DHCICLO (timestamp do último
-- ciclo lido). 45 injetoras com AD_MONITORADO='S', sinal vivo — aferido
-- 22/09/2026 16:45: 45 monitoradas, 1 parada há mais de 60 min.
--
-- DUAS ARMADILHAS:
--  1. AD_PARADAMAQUINA (a tabela "oficial" de parada, com MOTIVO codificado)
--     parou de ser alimentada em 31/10/2024. Não serve para tempo real.
--  2. TPRWCP.AD_ESTADOATUAL está 100% NULO. O estado declarado não existe —
--     o sinal confiável é o TEMPO DESDE O ÚLTIMO CICLO.
--
-- Consequência: este KPI diz QUE parou e HÁ QUANTO TEMPO, mas não diz POR QUÊ.
-- O motivo é justamente o que a cobrança pede ao gerente de produção.
--
-- Params: {{MIN_PARADA_ALERTA}}

WITH MON AS (
  SELECT NOME, AD_DHCICLO, AD_CICLOATUAL,
         ROUND((SYSDATE - AD_DHCICLO) * 24 * 60) AS MIN_SEM_CICLO
    FROM TPRWCP /*CC TPRWCP CC*/
   WHERE NVL(AD_MONITORADO,'N') = 'S'
)
SELECT
  COUNT(*)                                                          AS MONITORADAS,
  SUM(CASE WHEN MIN_SEM_CICLO > 15 THEN 1 ELSE 0 END)               AS PARADAS_15MIN,
  SUM(CASE WHEN MIN_SEM_CICLO > {{MIN_PARADA_ALERTA}} THEN 1 ELSE 0 END) AS PARADAS_60MIN,
  SUM(CASE WHEN AD_DHCICLO IS NULL THEN 1 ELSE 0 END)               AS SEM_SINAL,
  (SELECT LISTAGG(NOME || ' (' || MIN_SEM_CICLO || ' min)', ', ')
          WITHIN GROUP (ORDER BY MIN_SEM_CICLO DESC)
     FROM (SELECT NOME, MIN_SEM_CICLO FROM MON
            WHERE MIN_SEM_CICLO > {{MIN_PARADA_ALERTA}}
            ORDER BY MIN_SEM_CICLO DESC FETCH FIRST 12 ROWS ONLY))  AS LISTA
FROM MON
