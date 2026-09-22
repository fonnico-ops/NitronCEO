-- KPI: devolucoes
-- Pergunta: quanto do que faturei está voltando, e por quê?
--
-- ARMADILHA CONFIRMADA EM PRODUÇÃO (22/09/2026):
--   TIPMOV='D' cru infla a devolução em ~3x. No 3º tri/26 a composição era:
--     TOP 2203 "Devolução Simbólica Consignado"   R$ 1.426.216,82  <- NÃO é devolução
--     TOP 5205 "Devolução de Venda NF Própria"    R$   535.691,37
--     TOP 2201 "Devolução de Venda NF Própria"    R$   260.837,66
--     TOP 2206 "Devolução de Venda s/ Estoque"    R$    61.475,01
--     TOP 2215 "devolução site"                   R$    21.722,54
--   A 2203 é acerto de consignação, não retorno de cliente. Fica de fora.
--
-- O denominador usa a mesma âncora de faturamento do KPI faturamento_ritmo,
-- para que os dois números sejam comparáveis.
--
-- Params: {{CODEMP}}  {{JANELA_DIAS}}  {{TOPS_EXCLUIR_DEVOLUCAO}}

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
DEV AS (
  SELECT NVL(SUM(CAB.VLRNOTA),0) AS VLR, COUNT(*) AS NOTAS
    FROM TGFCAB CAB /*CC TGFCAB CC*/
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.TIPMOV = 'D'
     AND CAB.CODTIPOPER NOT IN ({{TOPS_EXCLUIR_DEVOLUCAO}})
     AND CAB.CODEMP IN ({{CODEMP}})
     AND CAB.DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
),
FAT AS (
  SELECT NVL(SUM(CAB.VLRNOTA),0) AS VLR
    FROM TGFCAB CAB
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
     AND CAB.CODEMP IN ({{CODEMP}})
     AND CAB.DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
)
SELECT
  D.NOTAS                                               AS NOTAS_DEVOLVIDAS,
  ROUND(D.VLR,2)                                        AS VLR_DEVOLVIDO,
  ROUND(F.VLR,2)                                        AS VLR_FATURADO,
  ROUND(D.VLR / NULLIF(F.VLR,0) * 100, 2)               AS PCT_SOBRE_FATURAMENTO
FROM DEV D CROSS JOIN FAT F
