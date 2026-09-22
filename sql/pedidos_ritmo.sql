-- KPI: pedidos_ritmo
-- Pergunta: a carteira que alimenta o mês que vem está entrando?
--
-- Âncora de pedido (skill §3): TGFTOP.TIPMOV='P' + AD_INSEREDASH='S'.
-- Compara o ritmo diário do mês corrente contra a média diária dos 90 dias
-- anteriores ao mês — base móvel, imune a mês cheio vs. mês parcial.
--
-- Params: {{CODEMP}}
-- Validado 22/09/2026: set/26 MTD 4.350 pedidos, R$ 4.331.656,45.

WITH TOPPED AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE TIPMOV = 'P' AND NVL(AD_INSEREDASH,'N') = 'S'
),
BASE AS (
  SELECT CAB.DTNEG, CAB.VLRNOTA
    FROM TGFCAB CAB /*CC TGFCAB CC*/
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPPED)
     AND CAB.CODEMP IN ({{CODEMP}})
     AND CAB.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
     AND CAB.DTNEG >= TRUNC(SYSDATE,'MM') - 90
),
ATUAL AS (
  SELECT NVL(SUM(VLRNOTA),0) AS VLR, COUNT(*) AS QTD,
         GREATEST(TRUNC(SYSDATE) - TRUNC(SYSDATE,'MM') + 1, 1) AS DIAS
    FROM BASE WHERE DTNEG >= TRUNC(SYSDATE,'MM')
),
HIST AS (
  SELECT NVL(SUM(VLRNOTA),0)/90 AS VLR_DIA, COUNT(*)/90 AS QTD_DIA
    FROM BASE WHERE DTNEG < TRUNC(SYSDATE,'MM')
)
SELECT
  ROUND(A.VLR,2)                                   AS VLR_MTD,
  A.QTD                                            AS QTD_MTD,
  ROUND(A.VLR / A.DIAS, 2)                         AS VLR_DIA_ATUAL,
  ROUND(H.VLR_DIA, 2)                              AS VLR_DIA_MEDIA_90D,
  ROUND(A.VLR / A.DIAS / NULLIF(H.VLR_DIA,0) * 100, 1) AS PCT_VS_MEDIA_90D
FROM ATUAL A CROSS JOIN HIST H
