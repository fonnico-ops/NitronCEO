-- KPI: cargas_montadas_dia
-- Pergunta: a expedição está escoando no ritmo da carteira?
--
-- FONTE: TGFORD (nativa, PK CODEMP+ORDEMCARGA). Viva — 48 ordens em 22/09/26.
-- NÃO usar AD_CARGADIARIA / AD_ORDENSCARGA / AD_PEDIDOSCARGA: pararam de ser
-- alimentadas em 20/05/2026. A skill de roteirização confirma: não reviver
-- essas tabelas sem decisão explícita.
--
-- SITUACAO: 'A' aberta, 'F' fechada. HORASAIDA preenchida em 95% das ordens.
-- Observado 14–22/09/26: 15, 22, 28, 90, 33, 5, 54, 48 ordens/dia.
--
-- Params: {{CODEMP}}

SELECT
  (SELECT COUNT(*) FROM TGFORD /*CC TGFORD CC*/
    WHERE CODEMP IN ({{CODEMP}})
      AND DTALTER >= TRUNC(SYSDATE)-1 AND DTALTER < TRUNC(SYSDATE))   AS ORDENS_ONTEM,
  (SELECT COUNT(*) FROM TGFORD
    WHERE CODEMP IN ({{CODEMP}}) AND SITUACAO = 'F'
      AND DTALTER >= TRUNC(SYSDATE)-1 AND DTALTER < TRUNC(SYSDATE))   AS FECHADAS_ONTEM,
  (SELECT ROUND(COUNT(*)/7,1) FROM TGFORD
    WHERE CODEMP IN ({{CODEMP}})
      AND DTALTER >= TRUNC(SYSDATE)-8 AND DTALTER < TRUNC(SYSDATE)-1) AS MEDIA_7D,
  (SELECT COUNT(*) FROM TGFORD
    WHERE CODEMP IN ({{CODEMP}}) AND SITUACAO = 'A'
      AND DTALTER < TRUNC(SYSDATE)-2)                                 AS ABERTAS_ATRASADAS
FROM DUAL
