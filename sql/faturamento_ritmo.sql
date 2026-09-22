-- KPI: faturamento_ritmo
-- Pergunta: no ritmo de hoje, fecho o mês na meta?
--
-- Metodologia (skill sankhya-especialista §2):
--   Âncora = TGFTOP.ATUALCOM='C' + AD_INSEREDASH='S'. NÃO usar TIPMOV='V':
--   isso descarta a TOP 3110 ("Pedido Especial"), que é faturamento real.
--   Filtro de TOP por subquery em CODTIPOPER — nunca JOIN na TGFTOP, que é
--   versionada por DHALTER e subconta ~65% do faturamento.
--   Métrica = SUM(VLRNOTA) de cabeçalho (inclui frete/IPI/ST).
--   Intercompany eliminado via TSIEMP.CODPARC.
--
-- Params: {{CODEMP}}  {{META_MENSAL}}
-- Validado 22/09/2026: set/26 MTD R$ 6.266.686,56 / 4.869 notas.

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
MTD AS (
  SELECT NVL(SUM(CAB.VLRNOTA),0) AS REALIZADO, COUNT(*) AS NOTAS
    FROM TGFCAB CAB /*CC TGFCAB CC*/
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
     AND CAB.CODEMP IN ({{CODEMP}})
     AND CAB.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
     AND CAB.DTNEG >= TRUNC(SYSDATE,'MM')
     AND CAB.DTNEG <  ADD_MONTHS(TRUNC(SYSDATE,'MM'),1)
),
DIAS AS (
  -- Dias úteis decorridos e totais do mês (seg-sex; feriado não tratado).
  SELECT
    SUM(CASE WHEN D <= TRUNC(SYSDATE) AND TO_CHAR(D,'DY','NLS_DATE_LANGUAGE=ENGLISH')
              NOT IN ('SAT','SUN') THEN 1 ELSE 0 END) AS UTEIS_DECORRIDOS,
    SUM(CASE WHEN TO_CHAR(D,'DY','NLS_DATE_LANGUAGE=ENGLISH')
              NOT IN ('SAT','SUN') THEN 1 ELSE 0 END) AS UTEIS_TOTAIS
  FROM (
    SELECT TRUNC(SYSDATE,'MM') + LEVEL - 1 AS D FROM DUAL
    CONNECT BY LEVEL <= TO_NUMBER(TO_CHAR(LAST_DAY(SYSDATE),'DD'))
  )
)
SELECT
  ROUND(M.REALIZADO,2)                                          AS REALIZADO_MTD,
  M.NOTAS                                                       AS NOTAS_MTD,
  D.UTEIS_DECORRIDOS,
  D.UTEIS_TOTAIS,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1), 2)        AS RITMO_DIA_UTIL,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1)
        * D.UTEIS_TOTAIS, 2)                                    AS PROJECAO_FECHAMENTO,
  {{META_MENSAL}}                                               AS META_MENSAL,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1)
        * D.UTEIS_TOTAIS / {{META_MENSAL}} * 100, 1)            AS PCT_PROJECAO_META
FROM MTD M CROSS JOIN DIAS D
