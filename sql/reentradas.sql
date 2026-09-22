-- KPI: reentradas
-- Pergunta: o que voltou, foi resolvido e refaturado — ou está parado?
--
-- TGFCAB.AD_REFATURADA='S' marca a nota que é refaturamento de uma devolução.
-- TGFCAB.AD_NUDEV guarda o vínculo com a devolução de origem.
-- Validado 22/09/2026: set/26 -> 17 notas refaturadas (R$ 186.222,34);
-- 58 notas com AD_NUDEV preenchido no mesmo mês.
--
-- A diferença entre as duas contagens é o estoque de casos em aberto: nota
-- devolvida que ainda não gerou refaturamento. É esse número que cobra a
-- qualidade, não o total de refaturamentos.
--
-- Params: {{CODEMP}}  {{JANELA_DIAS}}

SELECT
  (SELECT COUNT(*) FROM TGFCAB /*CC TGFCAB CC*/
    WHERE NVL(AD_REFATURADA,'N') = 'S' AND CODEMP IN ({{CODEMP}})
      AND DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}})            AS QTD_REFATURADAS,
  (SELECT ROUND(NVL(SUM(VLRNOTA),0),2) FROM TGFCAB
    WHERE NVL(AD_REFATURADA,'N') = 'S' AND CODEMP IN ({{CODEMP}})
      AND DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}})            AS VLR_REFATURADO,
  (SELECT COUNT(*) FROM TGFCAB
    WHERE AD_NUDEV IS NOT NULL AND CODEMP IN ({{CODEMP}})
      AND DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}})            AS QTD_COM_DEVOLUCAO_VINCULADA,
  (SELECT COUNT(*) FROM TGFCAB
    WHERE AD_NUDEV IS NOT NULL AND NVL(AD_REFATURADA,'N') <> 'S'
      AND CODEMP IN ({{CODEMP}})
      AND DTNEG >= TRUNC(SYSDATE) - {{JANELA_DIAS}})            AS QTD_EM_ABERTO
FROM DUAL
