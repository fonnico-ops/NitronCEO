-- KPI: fluxo_caixa_critico
-- Pergunta: fecha ou falta? E se falta, quanto e em que dia?
--
-- TGFFIN: RECDESP = 1 receita / -1 despesa. Título em aberto = DHBAIXA IS NULL.
-- PROVISAO='S' fica de fora — é lançamento previsto, não compromisso firme
-- (a skill alerta que o relatório dre_ano_atual herda inflação de provisão).
--
-- Aferido 22/09/2026 (Nitron, títulos em aberto, não-provisão):
--   D0–D7:  receber R$ 1.675.470,84 / pagar R$  1.817.828,24 -> gap   -142.357,40
--   D8–D30: receber R$ 5.676.974,53 / pagar R$ 13.426.196,66 -> gap -7.749.222,13
--
-- LIMITAÇÃO DECLARADA: isto é COMPROMISSO A VENCER, não saldo de caixa.
-- Não inclui o saldo bancário de abertura (TGFCTA/TGFMOV). Para virar um
-- fluxo de caixa de verdade, somar o saldo inicial — ver
-- docs/achados-de-dados.md, item "saldo de abertura".
--
-- Params: {{CODEMP}}

WITH FIN AS (
  SELECT RECDESP, DTVENC, VLRDESDOB
    FROM TGFFIN /*CC TGFFIN CC*/
   WHERE DHBAIXA IS NULL
     AND NVL(PROVISAO,'N') = 'N'
     AND CODEMP IN ({{CODEMP}})
     AND DTVENC >= TRUNC(SYSDATE)
     AND DTVENC <  TRUNC(SYSDATE) + 30
)
SELECT
  ROUND(NVL(SUM(CASE WHEN RECDESP=1  AND DTVENC < TRUNC(SYSDATE)+7
                     THEN VLRDESDOB END),0),2)                AS RECEBER_D0_D7,
  ROUND(NVL(SUM(CASE WHEN RECDESP=-1 AND DTVENC < TRUNC(SYSDATE)+7
                     THEN VLRDESDOB END),0),2)                AS PAGAR_D0_D7,
  ROUND(NVL(SUM(CASE WHEN DTVENC < TRUNC(SYSDATE)+7
                     THEN RECDESP * VLRDESDOB END),0),2)      AS SALDO_D0_D7,
  ROUND(NVL(SUM(CASE WHEN RECDESP=1  AND DTVENC >= TRUNC(SYSDATE)+7
                     THEN VLRDESDOB END),0),2)                AS RECEBER_D8_D30,
  ROUND(NVL(SUM(CASE WHEN RECDESP=-1 AND DTVENC >= TRUNC(SYSDATE)+7
                     THEN VLRDESDOB END),0),2)                AS PAGAR_D8_D30,
  ROUND(NVL(SUM(CASE WHEN DTVENC >= TRUNC(SYSDATE)+7
                     THEN RECDESP * VLRDESDOB END),0),2)      AS SALDO_D8_D30,
  ROUND(NVL(SUM(RECDESP * VLRDESDOB),0),2)                    AS SALDO_D0_D30
FROM FIN
