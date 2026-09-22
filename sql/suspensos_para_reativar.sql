-- KPI: suspensos_para_reativar
-- Pergunta: quais produtos suspensos continuam vendendo?
--
-- Existe uma lista de reativação com o PCP (Anderson) que não está no ERP.
-- Este KPI não substitui a lista — ele dá a ela um tamanho e um ranking, e
-- a cobrança pede que a lista seja publicada na resposta, com data e nome.
--
-- O sinal: produto com TGFPRO.AD_AG_SUSPENSO='S' que MESMO ASSIM vendeu nos
-- últimos 180 dias é candidato objetivo a voltar. Ou a venda é excepcional e
-- some, ou o produto foi suspenso e o mercado não concordou.
--
-- APURADO EM 22/09/2026:
--   652 produtos suspensos no cadastro
--   421 deles (65%) venderam nos últimos 180 dias — R$ 1.581.142,14
--   165 têm PEDIDO ABERTO agora, somando R$ 27.646,90
--
-- A métrica é o VALOR vendido, não a contagem: 421 itens é uma lista que
-- ninguém lê; os 20 primeiros por faturamento é uma reunião de meia hora.
--
-- Params: {{CODEMP}}  {{REATIVAR_PISO}}

WITH TOPQTD AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND ATUALEST = 'B' AND NVL(AD_INSEREDASH,'N') = 'S'
),
SUSP AS (
  SELECT CODPROD, DESCRPROD FROM TGFPRO
   WHERE NVL(AD_AG_SUSPENSO,'N') = 'S'
),
VENDA AS (
  SELECT I.CODPROD, SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR_180D
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPQTD)
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 180
   GROUP BY I.CODPROD
),
CART AS (
  SELECT I.CODPROD, SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR_CARTEIRA
    FROM TGFCAB C
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.TIPMOV = 'P' AND C.STATUSNOTA = 'L'
     AND NVL(C.PENDENTE,'N') = 'S'
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 45
   GROUP BY I.CODPROD
),
BASE AS (
  SELECT S.CODPROD, S.DESCRPROD,
         NVL(V.VLR_180D,0) AS VLR_180D,
         NVL(K.VLR_CARTEIRA,0) AS VLR_CARTEIRA
    FROM SUSP S
    LEFT JOIN VENDA V ON V.CODPROD = S.CODPROD
    LEFT JOIN CART  K ON K.CODPROD = S.CODPROD
),
AGG AS (
  SELECT COUNT(*) AS SUSPENSOS_TOTAL,
         SUM(CASE WHEN VLR_180D > 0 THEN 1 ELSE 0 END) AS COM_VENDA_180D,
         SUM(CASE WHEN VLR_CARTEIRA > 0 THEN 1 ELSE 0 END) AS COM_PEDIDO_ABERTO,
         ROUND(SUM(VLR_180D),2) AS VLR_VENDIDO_180D,
         ROUND(SUM(VLR_CARTEIRA),2) AS VLR_NA_CARTEIRA,
         SUM(CASE WHEN VLR_180D >= {{REATIVAR_PISO}} THEN 1 ELSE 0 END)
           AS CANDIDATOS_RELEVANTES
    FROM BASE
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR_180D DESC) AS LISTA
    FROM (SELECT B.VLR_180D,
                 B.DESCRPROD || ': R$ ' || ROUND(B.VLR_180D) || ' em 180d'
                   || CASE WHEN B.VLR_CARTEIRA > 0
                           THEN ' (R$ ' || ROUND(B.VLR_CARTEIRA) || ' em pedido agora)'
                           ELSE '' END AS TXT
            FROM BASE B
           WHERE B.VLR_180D > 0
           ORDER BY B.VLR_180D DESC FETCH FIRST 15 ROWS ONLY) X
)
SELECT A.SUSPENSOS_TOTAL, A.COM_VENDA_180D, A.COM_PEDIDO_ABERTO,
       A.VLR_VENDIDO_180D, A.VLR_NA_CARTEIRA, A.CANDIDATOS_RELEVANTES, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
