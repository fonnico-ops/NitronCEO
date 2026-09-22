-- KPI: performance_representante
-- Pergunta: quem está fora do ritmo e há quantos dias?
--
-- Compara cada representante no mês corrente (projetado para o mês cheio)
-- contra a própria média dos 3 meses anteriores.
--
-- Dois cortes que evitam cobrança injusta:
--   1. TGFVEN.ATIVO='S'  — representante desligado não entra no ranking.
--   2. MEDIA_3M >= {{PISO_RELEVANCIA}} — quem fatura trocado não vira alerta.
--
-- Params: {{CODEMP}}  {{PISO_META_PCT}}  {{PISO_RELEVANCIA}}
--
-- Aferido 22/09/2026 (piso R$ 5.000, meta 80%): 53 representantes relevantes,
-- 26 abaixo de 80% da própria média, 16 abaixo de 50%, 7 zerados no mês.
-- ATENÇÃO: no mesmo mês o faturamento TOTAL projeta 107% da média. Metade dos
-- representantes cai enquanto o total sobe = mudança de mix, não queda de
-- esforço. Por isso o KPI nasce em modo sombra — ver docs/achados-de-dados.md.

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
BASE AS (
  SELECT CAB.CODVEND, CAB.DTNEG, CAB.VLRNOTA
    FROM TGFCAB CAB /*CC TGFCAB CC*/
    JOIN TGFVEN VEN ON VEN.CODVEND = CAB.CODVEND AND NVL(VEN.ATIVO,'S') = 'S'
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
     AND CAB.CODEMP IN ({{CODEMP}})
     AND NVL(CAB.CODVEND,0) > 0
     AND CAB.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
     AND CAB.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-3)
),
POR_VEND AS (
  SELECT CODVEND,
         SUM(CASE WHEN DTNEG >= TRUNC(SYSDATE,'MM') THEN VLRNOTA ELSE 0 END) AS MTD,
         SUM(CASE WHEN DTNEG <  TRUNC(SYSDATE,'MM') THEN VLRNOTA ELSE 0 END)/3 AS MEDIA_3M
    FROM BASE GROUP BY CODVEND
),
PROJ AS (
  SELECT CODVEND, MTD, MEDIA_3M,
         MTD / GREATEST(TRUNC(SYSDATE)-TRUNC(SYSDATE,'MM')+1,1)
             * TO_NUMBER(TO_CHAR(LAST_DAY(SYSDATE),'DD')) AS PROJECAO
    FROM POR_VEND
   WHERE MEDIA_3M >= {{PISO_RELEVANCIA}}
)
SELECT
  (SELECT COUNT(*) FROM PROJ)                                      AS REPRESENTANTES,
  (SELECT COUNT(*) FROM PROJ
    WHERE PROJECAO < MEDIA_3M * {{PISO_META_PCT}}/100)             AS QTD_ABAIXO_META,
  (SELECT COUNT(*) FROM PROJ WHERE MTD = 0)                        AS QTD_ZERADOS,
  (SELECT LISTAGG(V.APELIDO || ' (' ||
            ROUND(P.PROJECAO/NULLIF(P.MEDIA_3M,0)*100) || '%)', ', ')
            WITHIN GROUP (ORDER BY P.PROJECAO/NULLIF(P.MEDIA_3M,0))
     FROM (SELECT * FROM PROJ
            WHERE PROJECAO < MEDIA_3M * {{PISO_META_PCT}}/100
            ORDER BY PROJECAO/NULLIF(MEDIA_3M,0) FETCH FIRST 10 ROWS ONLY) P
     LEFT JOIN TGFVEN V ON V.CODVEND = P.CODVEND)                  AS LISTA
FROM DUAL
