-- KPI: ecommerce_ritmo
-- Pergunta: o e-commerce está crescendo ou perdendo ritmo?
--
-- COMO O E-COMMERCE É IDENTIFICADO: pelas TOPs cuja descrição contém "Site"
-- e que são faturamento (ATUALCOM='C'). Não existe flag de canal para isso —
-- TGFCAB.AD_ORIGEM tem Representante, Força de Vendas, Farmer, Gestor e
-- Outside, e e-commerce não está entre eles. As TOPs vivas:
--   3226  Venda Site Mundo Ud                  21.506 notas em 180d
--   3248  Venda Site Nitron Clientes Especiais      2 notas
--   3231  Venda Site Hyak                           0
--   3232  Venda Site FULL ML                        0
--
-- HISTÓRICO MENSAL aferido em 22/09/2026:
--   mar/26    498 pedidos   R$  10.792   ticket R$ 21,67
--   abr/26  3.153           R$  79.405   ticket R$ 25,18
--   mai/26  3.805           R$  83.578   ticket R$ 21,97
--   jun/26  3.894           R$  87.309   ticket R$ 22,42
--   jul/26  3.096           R$  83.638   ticket R$ 27,01
--   ago/26  4.043           R$ 126.937   ticket R$ 31,40   <- melhor mês
--   set/26  3.257 (22 dias) R$  84.901   ticket R$ 26,07
--
-- O ticket subiu de R$ 22 para R$ 31 em agosto e recuou para R$ 26. Por isso
-- o KPI traz ticket junto com valor: crescer por volume de pedido barato e
-- crescer por ticket são coisas diferentes, e só a segunda escala.
--
-- PLATAFORMA: AD_PEDIDOSANY (integração Anymarket) traz MARKETPLACE e
-- ACCOUNTNAME por pedido. LIMITAÇÃO DECLARADA — a integração é NOVA: o
-- primeiro pedido é de 31/08/2026 (Shopee Mundo UD), 14/09 (Mercado Livre
-- Mundo UD) e 16/09 (Shopee Nitron). Antes disso não há quebra por
-- marketplace, então a coluna só faz sentido para o mês corrente.
--   SHOPEE Mundo UD        1.091 pedidos  R$ 19.850
--   SHOPEE Nitron            559          R$  9.070
--   MERCADO_LIVRE Mundo UD   172          R$  7.643   (taxa R$ 853)
--   MERCADO_LIVRE Nitron      23          R$  1.049   (taxa R$ 134)
--   Dos 1.845 pedidos do Anymarket, só 1.115 (60%) têm NUNOTA.
--
-- Params: {{EC_JANELA_DIAS}}

WITH TOPEC AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND UPPER(DESCROPER) LIKE '%SITE%'
   GROUP BY CODTIPOPER
),
V AS (
  SELECT C.DTNEG, C.NUNOTA, C.VLRNOTA
    FROM TGFCAB C /*CC TGFCAB CC*/
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPEC)
     AND C.DTNEG >= TRUNC(SYSDATE) - {{EC_JANELA_DIAS}}
),
MES AS (
  SELECT NVL(SUM(VLRNOTA),0) AS VLR, COUNT(*) AS PEDIDOS,
         GREATEST(TRUNC(SYSDATE) - TRUNC(SYSDATE,'MM') + 1, 1) AS DIAS
    FROM V WHERE DTNEG >= TRUNC(SYSDATE,'MM')
),
HIST AS (
  SELECT NVL(SUM(VLRNOTA),0)/{{EC_JANELA_DIAS}} AS VLR_DIA,
         COUNT(*)/{{EC_JANELA_DIAS}} AS PED_DIA,
         NVL(AVG(VLRNOTA),0) AS TICKET
    FROM V WHERE DTNEG < TRUNC(SYSDATE,'MM')
),
PLAT AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR DESC) AS LISTA
    FROM (SELECT SUM(A.TOTAL) AS VLR,
                 A.MARKETPLACE || ' / ' || A.ACCOUNTNAME || ': '
                   || COUNT(*) || ' pedidos, R$ ' || ROUND(SUM(A.TOTAL)) AS TXT
            FROM AD_PEDIDOSANY A
           WHERE A.CREATEDAT >= TRUNC(SYSDATE,'MM')
           GROUP BY A.MARKETPLACE, A.ACCOUNTNAME
           ORDER BY SUM(A.TOTAL) DESC FETCH FIRST 8 ROWS ONLY) X
)
SELECT
  ROUND(M.VLR,2)                                          AS VLR_MTD,
  M.PEDIDOS                                               AS PEDIDOS_MTD,
  ROUND(M.VLR / NULLIF(M.PEDIDOS,0), 2)                   AS TICKET_MTD,
  ROUND(H.TICKET, 2)                                      AS TICKET_MEDIO_HIST,
  ROUND(M.VLR / M.DIAS, 2)                                AS VLR_DIA_ATUAL,
  ROUND(H.VLR_DIA, 2)                                     AS VLR_DIA_HIST,
  ROUND(M.VLR / M.DIAS / NULLIF(H.VLR_DIA,0) * 100, 1)    AS PCT_VS_MEDIA,
  P.LISTA
FROM MES M CROSS JOIN HIST H CROSS JOIN PLAT P
