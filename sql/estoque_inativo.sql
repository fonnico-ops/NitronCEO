-- KPI: estoque_inativo
-- Pergunta: quanto de capital está parado em produto que saiu de linha?
--
-- Produto com TGFPRO.ATIVO='N' que ainda tem saldo é dinheiro imobilizado em
-- algo que a empresa decidiu não vender mais. Ou se liquida, ou se assume a
-- perda — o que não dá é ficar ocupando endereço no CD.
--
-- ATIVO='N' é diferente de AD_AG_SUSPENSO='S':
--   ATIVO='N'           1.353 produtos — saiu do cadastro, não se vende mais
--   AD_AG_SUSPENSO='S'    652 produtos — suspenso, pode voltar
--                               (ver suspensos_para_reativar.sql)
-- Os dois se cruzam em 79 produtos. Este KPI olha ATIVO='N'.
--
-- CUSTO: TGFCUS.CUSMED da última DTATUAL por produto. A tabela é histórica
-- (chave CODPROD+CODEMP+DTATUAL+CODLOCAL+CONTROLE), então pegar sem o
-- KEEP DENSE_RANK LAST soma custo de várias datas.
--
-- A COLUNA QUE SEPARA LIQUIDAÇÃO DE SUCATA: produto inativo que ainda vendeu
-- nos últimos 180 dias tem mercado e sai com desconto; o que não vendeu nada
-- é decisão de baixa, não de promoção. São conversas diferentes e a ação
-- pede as duas separadas.
--
-- APURADO EM 22/09/2026 (saldo das empresas 2, 4 e 14, sem a conta de
-- transferência): 57 produtos inativos com saldo, 304.723 unidades,
-- R$ 607.635,72 a custo médio. 8 deles não têm custo cadastrado e entram
-- com zero — o valor real é um pouco maior.
--
-- Params: {{CODEMP}}  {{CODEMP_SALDO}}  {{LOCAL_TRANSFERENCIA}}
--         {{ESTOQUE_INATIVO_PISO}}

WITH SALDO AS (
  SELECT CODPROD, SUM(NVL(ESTOQUE,0)) AS QTD
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}})
     AND CODLOCAL <> {{LOCAL_TRANSFERENCIA}}
     AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
  HAVING SUM(NVL(ESTOQUE,0)) > 0
),
CUSTO AS (
  SELECT CODPROD,
         MAX(CUSMED) KEEP (DENSE_RANK LAST ORDER BY DTATUAL) AS CUSMED
    FROM TGFCUS WHERE CODEMP IN (1,2) GROUP BY CODPROD
),
VENDA AS (
  SELECT I.CODPROD, SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR_180D
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TGFTOP
                           WHERE ATUALCOM = 'C' AND ATUALEST = 'B'
                             AND NVL(AD_INSEREDASH,'N') = 'S')
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 180
   GROUP BY I.CODPROD
),
BASE AS (
  SELECT P.CODPROD, P.DESCRPROD, S.QTD,
         S.QTD * NVL(C.CUSMED,0) AS VLR,
         NVL(V.VLR_180D,0) AS VLR_VENDIDO,
         CASE WHEN NVL(C.CUSMED,0) = 0 THEN 1 ELSE 0 END AS SEM_CUSTO
    FROM SALDO S
    JOIN TGFPRO P ON P.CODPROD = S.CODPROD AND NVL(P.ATIVO,'S') = 'N'
    LEFT JOIN CUSTO C ON C.CODPROD = S.CODPROD
    LEFT JOIN VENDA V ON V.CODPROD = S.CODPROD
),
AGG AS (
  SELECT COUNT(*) AS PRODUTOS,
         ROUND(SUM(QTD)) AS QTD_TOTAL,
         ROUND(SUM(VLR),2) AS VLR_CUSTO,
         ROUND(SUM(CASE WHEN VLR_VENDIDO > 0 THEN VLR ELSE 0 END),2) AS VLR_LIQUIDAVEL,
         ROUND(SUM(CASE WHEN VLR_VENDIDO = 0 THEN VLR ELSE 0 END),2) AS VLR_SEM_MERCADO,
         SUM(CASE WHEN VLR_VENDIDO > 0 THEN 1 ELSE 0 END) AS COM_VENDA_180D,
         SUM(SEM_CUSTO) AS SEM_CUSTO_CADASTRADO
    FROM BASE
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR DESC) AS LISTA
    FROM (SELECT B.VLR,
                 B.DESCRPROD || ': ' || ROUND(B.QTD) || ' un, R$ ' || ROUND(B.VLR)
                   || CASE WHEN B.VLR_VENDIDO > 0 THEN ' (ainda vende)'
                           ELSE ' (sem venda em 180d)' END AS TXT
            FROM BASE B
           WHERE B.VLR >= {{ESTOQUE_INATIVO_PISO}}
           ORDER BY B.VLR DESC FETCH FIRST 15 ROWS ONLY) X
)
SELECT A.PRODUTOS, A.QTD_TOTAL, A.VLR_CUSTO, A.VLR_LIQUIDAVEL, A.VLR_SEM_MERCADO,
       A.COM_VENDA_180D, A.SEM_CUSTO_CADASTRADO, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
