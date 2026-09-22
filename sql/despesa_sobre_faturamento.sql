-- KPI: despesa_sobre_faturamento
-- Pergunta: a despesa está crescendo mais rápido que a receita?
--
-- NASCE EM SOMBRA, e o motivo é o próprio numerador.
--
-- A despesa bruta da TGFFIN (RECDESP=-1, não-provisão) roda entre R$ 10,6 mi
-- e R$ 15,2 mi por mês, contra um faturamento de R$ 7,5 mi. A razão passa de
-- 190% — o que não significa que a empresa perde dinheiro, e sim que os dois
-- lados não são comparáveis:
--   - a despesa inclui matéria-prima, empréstimos, dividendos e impostos;
--   - inclui as 7 empresas do recorte, com movimento entre elas;
--   - o faturamento usa a âncora ATUALCOM='C', que é só receita de venda.
--
-- O QUE FALTA PARA ATIVAR: definir com a controladoria quais naturezas
-- compõem "despesa operacional" (excluindo 4010203 Empréstimos, 7010101
-- Lucros e Dividendos, 8010700 Adiantamentos e as naturezas de imposto).
-- Com essa lista, um parâmetro NAT_OPERACIONAL passa a filtrar e o KPI sai
-- da sombra com um percentual que significa alguma coisa.
--
-- Enquanto isso, o KPI mede a TENDÊNCIA da razão contra os 12 meses
-- anteriores — que é comparável consigo mesma mesmo com o escopo errado, e
-- por isso já aparece no pulso do CEO.
--
-- Histórico da despesa bruta mensal (set/25 a ago/26), aferido 22/09/2026:
--   10,67 | 12,80 | 11,79 | 10,78 | 10,69 | 11,79 | 15,22 | 12,58 | 15,19
--   14,03 | 12,72 | 14,38  (milhões)
--
-- Params: {{CODEMP}}

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
MES AS (
  SELECT
    (SELECT NVL(SUM(F.VLRDESDOB),0) FROM TGFFIN F
      WHERE F.CODEMP IN ({{CODEMP}}) AND F.RECDESP = -1
        AND NVL(F.PROVISAO,'N') = 'N'
        AND F.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
        AND F.DTNEG <  TRUNC(SYSDATE,'MM'))                      AS DESP_MES,
    (SELECT NVL(SUM(C.VLRNOTA),0) FROM TGFCAB C
      WHERE C.CODEMP IN ({{CODEMP}}) AND C.STATUSNOTA = 'L'
        AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
        AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
        AND C.DTNEG <  TRUNC(SYSDATE,'MM'))                      AS FAT_MES,
    (SELECT NVL(SUM(F.VLRDESDOB),0)/12 FROM TGFFIN F
      WHERE F.CODEMP IN ({{CODEMP}}) AND F.RECDESP = -1
        AND NVL(F.PROVISAO,'N') = 'N'
        AND F.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-13)
        AND F.DTNEG <  ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1))       AS DESP_MEDIA,
    (SELECT NVL(SUM(C.VLRNOTA),0)/12 FROM TGFCAB C
      WHERE C.CODEMP IN ({{CODEMP}}) AND C.STATUSNOTA = 'L'
        AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
        AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-13)
        AND C.DTNEG <  ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1))       AS FAT_MEDIA
  FROM DUAL
)
SELECT
  ROUND(DESP_MES,2)                                              AS DESPESA_MES,
  ROUND(FAT_MES,2)                                               AS FATURAMENTO_MES,
  ROUND(DESP_MES / NULLIF(FAT_MES,0) * 100, 1)                   AS PCT_MES,
  ROUND(DESP_MEDIA / NULLIF(FAT_MEDIA,0) * 100, 1)               AS PCT_MEDIA_12M,
  ROUND(DESP_MES / NULLIF(FAT_MES,0)
        / NULLIF(DESP_MEDIA / NULLIF(FAT_MEDIA,0),0) * 100, 1)   AS PCT_VS_PADRAO
FROM MES
