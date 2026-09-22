-- KPI: produtos_em_queda
-- Pergunta: o que vendia bem e parou de vender?
--
-- Compara os últimos 90 dias contra os 90 anteriores, por produto, em VALOR.
--
-- O corte {{QUEDA_PISO_BASE}} é o que separa notícia de ruído: só entra
-- produto que TINHA performance no período anterior. Produto que vendeu
-- R$ 300 e caiu para R$ 100 é variação normal de cauda longa; produto que
-- vendia R$ 80 mil e caiu para R$ 20 mil é cliente perdido, concorrente
-- entrando ou ruptura crônica — e é isso que o comercial precisa explicar.
--
-- Usa ATUALEST='B' junto com ATUALCOM='C' para não deixar a TOP 3110
-- (que duplica valor de propósito) criar queda ou alta fantasma quando um
-- pedido especial cai de um período para o outro.
--
-- Aferido 22/09/2026 (piso R$ 20 mil no período base):
--   1.071 produtos com movimento | 129 caíram mais de 30% | 70 caíram mais
--   de 50% | 7 pararam de vender | R$ 3.921.906,88 de receita a menos que o
--   mesmo produto gerava no período anterior.
--
-- Params: {{CODEMP}}  {{QUEDA_PISO_BASE}}  {{QUEDA_PCT}}

WITH TOPQTD AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND ATUALEST = 'B' AND NVL(AD_INSEREDASH,'N') = 'S'
),
V AS (
  SELECT I.CODPROD, C.DTNEG, I.VLRTOT - NVL(I.VLRDESC,0) AS VLR
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPQTD)
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 180
),
P AS (
  SELECT CODPROD,
         SUM(CASE WHEN DTNEG >= TRUNC(SYSDATE)-90 THEN VLR ELSE 0 END) AS VLR_90,
         SUM(CASE WHEN DTNEG <  TRUNC(SYSDATE)-90 THEN VLR ELSE 0 END) AS VLR_ANT
    FROM V GROUP BY CODPROD
),
QUEDA AS (
  SELECT CODPROD, VLR_90, VLR_ANT, VLR_ANT - VLR_90 AS PERDA,
         VLR_90 / NULLIF(VLR_ANT,0) * 100 AS PCT_RESTANTE
    FROM P
   WHERE VLR_ANT >= {{QUEDA_PISO_BASE}}
     AND VLR_90 < VLR_ANT * {{QUEDA_PCT}}/100
),
AGG AS (
  SELECT COUNT(*) AS PRODUTOS_EM_QUEDA,
         ROUND(NVL(SUM(PERDA),0),2) AS VLR_PERDIDO,
         SUM(CASE WHEN VLR_90 = 0 THEN 1 ELSE 0 END) AS PARARAM_DE_VENDER,
         SUM(CASE WHEN PCT_RESTANTE < 50 THEN 1 ELSE 0 END) AS QUEDA_ACIMA_50PCT
    FROM QUEDA
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.PERDA DESC) AS LISTA
    FROM (SELECT Q.PERDA,
                 P.DESCRPROD || ': R$ ' || ROUND(Q.VLR_ANT) || ' -> R$ '
                   || ROUND(Q.VLR_90) || ' (' || ROUND(NVL(Q.PCT_RESTANTE,0))
                   || '%)' AS TXT
            FROM QUEDA Q JOIN TGFPRO P ON P.CODPROD = Q.CODPROD
           ORDER BY Q.PERDA DESC FETCH FIRST 12 ROWS ONLY) X
)
SELECT A.PRODUTOS_EM_QUEDA, A.VLR_PERDIDO, A.PARARAM_DE_VENDER,
       A.QUEDA_ACIMA_50PCT, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
