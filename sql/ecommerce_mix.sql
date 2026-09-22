-- KPI: ecommerce_mix
-- Pergunta: o catálogo do e-commerce está concentrado ou disperso demais?
--
-- Responde às duas pontas de uma vez — o que mais vende e o que menos vende —
-- porque as duas são a mesma decisão: onde colocar foto, anúncio, verba de
-- mídia e estoque.
--
-- APURADO EM 22/09/2026 (90 dias, TOPs de Site):
--   382 SKUs vendidos, R$ 309.402,02
--    90 SKUs (23,6%) fazem 80% da receita
--   120 SKUs venderam MENOS DE R$ 100 em 90 dias, somando R$ 5.700,38 —
--       1,8% da receita em 31% do catálogo ativo
--    83 SKUs venderam até 2 unidades no trimestre
--
-- A cauda não é de graça: cada SKU tem foto, descrição, anúncio em cada
-- marketplace e espaço de estoque. 120 itens que somam R$ 5.700 em três meses
-- custam mais atenção do que devolvem.
--
-- A MÉTRICA É A CAUDA, não a concentração. Concentração alta é normal e
-- saudável no varejo online; o que se cobra é a decisão sobre o que não
-- vende — sobe verba, corrige preço, ou sai do ar.
--
-- Params: {{EC_JANELA_MIX_DIAS}}  {{EC_CAUDA_PISO}}

WITH TOPEC AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND UPPER(DESCROPER) LIKE '%SITE%'
   GROUP BY CODTIPOPER
),
ITENS AS (
  SELECT I.CODPROD, SUM(I.QTDNEG) AS QTD,
         SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPEC)
     AND C.DTNEG >= TRUNC(SYSDATE) - {{EC_JANELA_MIX_DIAS}}
   GROUP BY I.CODPROD
),
RANQUE AS (
  SELECT CODPROD, QTD, VLR,
         SUM(VLR) OVER (ORDER BY VLR DESC) AS ACUM,
         SUM(VLR) OVER () AS TOTAL,
         ROW_NUMBER() OVER (ORDER BY VLR DESC) AS POS
    FROM ITENS
),
AGG AS (
  SELECT COUNT(*) AS SKUS_VENDIDOS,
         ROUND(MAX(TOTAL),2) AS VLR_TOTAL,
         MIN(CASE WHEN ACUM >= TOTAL * 0.8 THEN POS END) AS SKUS_ATE_80PCT,
         SUM(CASE WHEN VLR < {{EC_CAUDA_PISO}} THEN 1 ELSE 0 END) AS SKUS_CAUDA,
         ROUND(SUM(CASE WHEN VLR < {{EC_CAUDA_PISO}} THEN VLR ELSE 0 END),2) AS VLR_CAUDA,
         SUM(CASE WHEN QTD <= 2 THEN 1 ELSE 0 END) AS SKUS_ATE_2_UNID
    FROM RANQUE
),
CAMPEOES AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR DESC) AS LISTA
    FROM (SELECT R.VLR,
                 P.DESCRPROD || ': R$ ' || ROUND(R.VLR) || ' ('
                   || ROUND(R.QTD) || ' un)' AS TXT
            FROM RANQUE R JOIN TGFPRO P ON P.CODPROD = R.CODPROD
           WHERE R.POS <= 10 ORDER BY R.VLR DESC) X
),
LANTERNA AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR) AS LISTA
    FROM (SELECT R.VLR,
                 P.DESCRPROD || ': R$ ' || ROUND(R.VLR,2) AS TXT
            FROM RANQUE R JOIN TGFPRO P ON P.CODPROD = R.CODPROD
           WHERE R.VLR < {{EC_CAUDA_PISO}}
           ORDER BY R.VLR FETCH FIRST 10 ROWS ONLY) X
)
SELECT A.SKUS_VENDIDOS, A.VLR_TOTAL, A.SKUS_ATE_80PCT, A.SKUS_CAUDA,
       A.VLR_CAUDA, A.SKUS_ATE_2_UNID,
       C.LISTA AS LISTA, L.LISTA AS LISTA_CAUDA
  FROM AGG A CROSS JOIN CAMPEOES C CROSS JOIN LANTERNA L
