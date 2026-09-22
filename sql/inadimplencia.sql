-- KPI: inadimplencia
-- Pergunta: quanto já venceu e não entrou?
--
-- Aferido 22/09/2026: R$ 9.728.499,68 em 3.352 títulos vencidos nos últimos
-- 365 dias (Nitron, em aberto, não-provisão).
--
-- O corte de 365 dias é deliberado: sem ele entram títulos antigos já
-- baixados contabilmente por outra via, que inflam o número e tiram a
-- credibilidade da cobrança.
--
-- Params: {{CODEMP}}  {{JANELA_VENCIDO_DIAS}}

WITH VENC AS (
  SELECT F.CODPARC, F.VLRDESDOB, F.DTVENC,
         TRUNC(SYSDATE) - TRUNC(F.DTVENC) AS DIAS_ATRASO
    FROM TGFFIN F /*CC TGFFIN CC*/
   WHERE F.DHBAIXA IS NULL
     AND F.RECDESP = 1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.CODEMP IN ({{CODEMP}})
     AND F.DTVENC <  TRUNC(SYSDATE)
     AND F.DTVENC >= TRUNC(SYSDATE) - {{JANELA_VENCIDO_DIAS}}
     AND F.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
)
SELECT
  COUNT(*)                                                       AS TITULOS,
  ROUND(NVL(SUM(VLRDESDOB),0),2)                                 AS VLR_VENCIDO,
  ROUND(NVL(SUM(CASE WHEN DIAS_ATRASO <= 30 THEN VLRDESDOB END),0),2)  AS VLR_ATE_30D,
  ROUND(NVL(SUM(CASE WHEN DIAS_ATRASO > 90 THEN VLRDESDOB END),0),2)   AS VLR_ACIMA_90D,
  (SELECT LISTAGG(P.NOMEPARC || ' (R$ ' || ROUND(X.VLR) || ')', ', ')
          WITHIN GROUP (ORDER BY X.VLR DESC)
     FROM (SELECT CODPARC, SUM(VLRDESDOB) AS VLR FROM VENC
            GROUP BY CODPARC ORDER BY SUM(VLRDESDOB) DESC
            FETCH FIRST 10 ROWS ONLY) X
     JOIN TGFPAR P ON P.CODPARC = X.CODPARC)                     AS LISTA
FROM VENC
