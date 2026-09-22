-- KPI: ruptura_estoque
-- Pergunta: quanto de venda está parada esperando o PCP produzir?
--
-- DEMANDA: carteira roteirizável, na definição da skill de roteirização —
--   TIPMOV='P', STATUSNOTA='L', PENDENTE='S', sem ordem de carga,
--   com corte temporal (existem ~27 mil pedidos pendentes desde 2020;
--   sem o corte a análise vira arqueologia).
--
-- SALDO: TGFEST somado por CODPROD.
--
-- POR QUE ESTE KPI NASCE EM SOMBRA — quatro problemas de dado, todos
-- confirmados em produção em 22/09/2026:
--   1. TGFEST na CODEMP 1 tem 12,5 MILHÕES de linhas e soma 3×10^19 unidades.
--      Dado histórico corrompido, inutilizável como saldo.
--   2. CODEMP 4 (-248.978) e CODEMP 14 (-428.911) somam saldo NEGATIVO.
--   3. TGFEST.QTDPEDPENDEST está 100% zerado — não serve como demanda.
--   4. Pedido que falta no CD (CODEMP 2) mas tem saldo na produção NÃO é
--      ruptura: é transferência interna do mesmo endereço.
--
-- Com {{CODEMP_SALDO}}=2 o resultado em 22/09/26 foi 460 itens sem saldo e
-- R$ 1.577.274,91 de carteira exposta — número alto demais para cobrar o PCP
-- sem antes acordar qual empresa é a fonte de saldo por linha de produto.
--
-- Params: {{CODEMP}}  {{CODEMP_SALDO}}  {{CARTEIRA_DIAS}}

WITH CARTEIRA AS (
  SELECT I.CODPROD,
         SUM(I.QTDNEG) AS QTD_PEDIDA,
         SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.TIPMOV = 'P'
     AND C.STATUSNOTA = 'L'
     AND NVL(C.PENDENTE,'N') = 'S'
     AND NVL(C.ORDEMCARGA,0) = 0
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - {{CARTEIRA_DIAS}}
   GROUP BY I.CODPROD
),
SALDO AS (
  -- Saldo físico, não ESTOQUE-RESERVADO: RESERVADO já contém os pedidos
  -- pendentes que estamos avaliando, e subtrair duas vezes manda pedido bom
  -- para a fila de ruptura.
  SELECT CODPROD, SUM(NVL(ESTOQUE,0)) AS FISICO
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}}) AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
)
SELECT
  (SELECT COUNT(*) FROM CARTEIRA)                                    AS ITENS_CARTEIRA,
  (SELECT COUNT(*) FROM CARTEIRA C LEFT JOIN SALDO S ON S.CODPROD=C.CODPROD
    WHERE NVL(S.FISICO,0) <= 0)                                      AS ITENS_SEM_SALDO,
  (SELECT COUNT(*) FROM CARTEIRA C LEFT JOIN SALDO S ON S.CODPROD=C.CODPROD
    WHERE NVL(S.FISICO,0) > 0 AND NVL(S.FISICO,0) < C.QTD_PEDIDA)    AS ITENS_SALDO_PARCIAL,
  (SELECT ROUND(NVL(SUM(C.VLR),0),2) FROM CARTEIRA C
     LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
    WHERE NVL(S.FISICO,0) < C.QTD_PEDIDA)                            AS VLR_EM_RISCO,
  (SELECT LISTAGG(P.DESCRPROD || ' (R$ ' || ROUND(X.VLR) || ')', ', ')
          WITHIN GROUP (ORDER BY X.VLR DESC)
     FROM (SELECT C.CODPROD, C.VLR FROM CARTEIRA C
             LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
            WHERE NVL(S.FISICO,0) <= 0
            ORDER BY C.VLR DESC FETCH FIRST 10 ROWS ONLY) X
     JOIN TGFPRO P ON P.CODPROD = X.CODPROD)                         AS LISTA
FROM DUAL
