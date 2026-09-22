-- KPI: emissao_ntrlog
-- Pergunta: a NTR Log está faturando o frete que a Nitron paga a ela?
--
-- NTR LOG = CODEMP 3, CODPARC 65253 (TSIEMP). É empresa do grupo, dentro do
-- recorte "Nitron" (1,2,3,4,14,17,20) — por isso some nas consolidações que
-- eliminam intercompany, e por isso esta lacuna passou despercebida.
--
-- O KPI cruza as duas pontas da mesma operação:
--   LADO A — o que a Nitron LANÇA como frete NTR:
--     TGFFIN, CODNAT {{NAT_FRETE_NTR}} ("Despesas c/ fretes e transportes
--     NTR"), RECDESP=-1, CODPARC 65253.
--   LADO B — o que a NTR Log EMITE:
--     TGFCAB da CODEMP 3, saída liberada.
--
-- APURADO EM 22/09/2026 — o lado A por mês (todos os meses ~97% BAIXADOS,
-- ou seja, dinheiro que saiu de verdade):
--     mar/26  680 títulos  R$ 792.376,86      set/26  561 títulos  R$ 600.449,66
--     abr/26  708 títulos  R$ 812.491,40      ago/26  636 títulos  R$ 842.709,40
--     mai/26  534 títulos  R$ 675.456,23      jul/26  552 títulos  R$ 774.065,20
--     jun/26  571 títulos  R$ 799.055,02
--   O lado B, no mesmo período: R$ 21 mil a R$ 29 mil por mês.
--
--   E o achado que sustenta o KPI: dos 4.242 títulos de frete NTR nos últimos
--   6 meses, ZERO tem NUNOTA preenchido. Nenhum está amarrado a nota fiscal
--   dentro do ERP.
--
-- LIMITE DO QUE ISTO PROVA: o ERP mostra despesa lançada e paga sem nota
-- vinculada. Não prova que a nota não existe — pode ter sido emitida na
-- prefeitura e nunca importada para cá. Essa é exatamente a pergunta que a
-- ação manda o financeiro responder, e é por isso que a ação pede a
-- conciliação, não a conclusão.
--
-- Params: {{CODEMP}}  {{NAT_FRETE_NTR}}  {{CODPARC_NTRLOG}}  {{CODEMP_NTRLOG}}

WITH PAGO AS (
  SELECT NVL(SUM(F.VLRDESDOB),0) AS VLR,
         COUNT(*) AS TITULOS,
         SUM(CASE WHEN F.NUNOTA IS NULL THEN 1 ELSE 0 END) AS SEM_NOTA
    FROM TGFFIN F /*CC TGFFIN CC*/
   WHERE F.CODNAT = {{NAT_FRETE_NTR}}
     AND F.RECDESP = -1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.CODPARC = {{CODPARC_NTRLOG}}
     AND F.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
     AND F.DTNEG <  TRUNC(SYSDATE,'MM')
),
EMITIDO AS (
  SELECT NVL(SUM(C.VLRNOTA),0) AS VLR, COUNT(*) AS NOTAS
    FROM TGFCAB C /*CC TGFCAB CC*/
   WHERE C.CODEMP = {{CODEMP_NTRLOG}}
     AND C.STATUSNOTA = 'L'
     AND C.TIPMOV IN ('V','S')
     AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
     AND C.DTNEG <  TRUNC(SYSDATE,'MM')
)
SELECT
  ROUND(P.VLR,2)                                        AS FRETE_PAGO_MES,
  P.TITULOS                                             AS TITULOS_FRETE,
  P.SEM_NOTA                                            AS TITULOS_SEM_NOTA,
  ROUND(E.VLR,2)                                        AS EMITIDO_NTRLOG,
  E.NOTAS                                               AS NOTAS_EMITIDAS,
  ROUND(P.VLR - E.VLR, 2)                               AS GAP_EMISSAO,
  ROUND(E.VLR / NULLIF(P.VLR,0) * 100, 1)               AS PCT_COBERTURA
FROM PAGO P CROSS JOIN EMITIDO E
