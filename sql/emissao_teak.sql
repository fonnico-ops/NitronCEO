-- KPI: emissao_teak
-- Pergunta: a Teak Brazil parou de emitir?
--
-- TEAK BRAZIL = CODEMP 8 (São Paulo) e 21 (Rondônia), mesma razão social.
-- Fora do recorte "Nitron", então não aparece em nenhum dos outros KPIs.
--
-- Aferido 22/09/2026 (CODEMP 8, TOPs ATUALCOM='C'):
--     mar/26   5 notas  R$ 119.537,71      jul/26  13 notas  R$ 298.119,32
--     abr/26   2 notas  R$ 272.792,00      ago/26  18 notas  R$ 321.095,22
--     mai/26   1 nota   R$  19.830,40      set/26  10 notas  R$ 170.882,56
--     jun/26  11 notas  R$ 240.806,91
--   CODEMP 21 (Rondônia): ZERO emissão em 6 meses.
--
-- A métrica é DIAS_SEM_EMITIR, não o valor: o padrão da Teak é irregular por
-- natureza (5 notas num mês, 18 no outro), então cobrar variação de valor
-- geraria alarme toda semana. O que é anômalo é o silêncio — mai/26 teve
-- uma nota só, e isso deveria ter sido percebido na época.
--
-- Params: {{CODEMP_TEAK}}  {{JANELA_DIAS}}

WITH NOTAS AS (
  SELECT C.CODEMP, C.DTNEG, C.VLRNOTA
    FROM TGFCAB C /*CC TGFCAB CC*/
   WHERE C.CODEMP IN ({{CODEMP_TEAK}})
     AND C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TGFTOP WHERE ATUALCOM = 'C')
     AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-6)
),
AGG AS (
  SELECT
    NVL(TRUNC(SYSDATE) - MAX(TRUNC(DTNEG)), 999)                  AS DIAS_SEM_EMITIR,
    COUNT(CASE WHEN DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}} THEN 1 END)
                                                                  AS NOTAS_JANELA,
    ROUND(NVL(SUM(CASE WHEN DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
                       THEN VLRNOTA END),0),2)                    AS VLR_JANELA,
    ROUND(NVL(SUM(VLRNOTA),0)/6, 2)                               AS MEDIA_MES_6M
  FROM NOTAS
),
POR_EMP AS (
  SELECT LISTAGG(X.TXT, ' | ') WITHIN GROUP (ORDER BY X.CODEMP) AS LISTA
    FROM (SELECT E.CODEMP,
                 E.NOMEFANTASIA || ': ' || NVL(N.QTD,0) || ' notas em 6 meses' AS TXT
            FROM TSIEMP E
            LEFT JOIN (SELECT CODEMP, COUNT(*) AS QTD FROM NOTAS GROUP BY CODEMP) N
                   ON N.CODEMP = E.CODEMP
           WHERE E.CODEMP IN ({{CODEMP_TEAK}})) X
)
SELECT A.DIAS_SEM_EMITIR, A.NOTAS_JANELA, A.VLR_JANELA, A.MEDIA_MES_6M, P.LISTA
  FROM AGG A CROSS JOIN POR_EMP P
