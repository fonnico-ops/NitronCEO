-- KPI: injecao_terceirizada
-- Pergunta: quanto custa ter molde injetando fora, e com quem?
--
-- Existe a intenção de trazer moldes de terceiros para dentro. Este KPI não
-- diz QUAL molde está onde — o ERP não guarda isso: AD_APONTACICLO tem o
-- campo LOCALINJECAO com o domínio CDI:Construplast | Nitron | Tanamu, mas
-- em 180 dias TODAS as 2.628 OPs foram apontadas como "Nitron". A produção
-- terceirizada não passa pelo apontamento.
--
-- O que o ERP guarda é o CUSTO, na natureza {{NAT_INJECAO_TERCEIRIZADA}}
-- ("Injeção Tercerizada"), por fornecedor. Isso basta para dimensionar a
-- decisão e para cobrar o plano de internalização.
--
-- APURADO EM 22/09/2026 — últimos 12 meses:
--   TANAMU                            R$ 3.195.053  (R$ 862.655 no trimestre)
--   MAGIC TOYS DO BRASIL              R$   465.390  (R$ 424.120 no trimestre)
--   L PLAST FERRAMENTARIA             R$   253.404
--   J KOVACS                          R$   237.291
--   TEMPOS DE BRASIL TERCEIRIZACAO    R$   120.061
--   TRINPLAST METADIL                 R$    94.215
--   TOTAL                             R$ 4.400.168  em 12 meses
--   Tanamu sozinha é 73% do gasto.
--
-- A métrica é o custo do TRIMESTRE, não o de 12 meses: o número de 12 meses
-- é história e não muda com ação; o do trimestre responde se a
-- internalização está acontecendo.
--
-- Params: {{NAT_INJECAO_TERCEIRIZADA}}

WITH GASTO AS (
  SELECT F.CODPARC, F.DTNEG, F.VLRDESDOB
    FROM TGFFIN F /*CC TGFFIN CC*/
   WHERE F.CODNAT = {{NAT_INJECAO_TERCEIRIZADA}}
     AND F.RECDESP = -1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-12)
),
AGG AS (
  SELECT
    ROUND(NVL(SUM(CASE WHEN DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-3)
                       THEN VLRDESDOB END),0),2)                 AS VLR_TRIMESTRE,
    ROUND(NVL(SUM(VLRDESDOB),0),2)                               AS VLR_12M,
    ROUND(NVL(SUM(CASE WHEN DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-12)
                       AND DTNEG < ADD_MONTHS(TRUNC(SYSDATE,'MM'),-9)
                       THEN VLRDESDOB END),0),2)                 AS VLR_TRIM_ANO_PASSADO,
    COUNT(DISTINCT CODPARC)                                      AS FORNECEDORES
  FROM GASTO
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR DESC) AS LISTA
    FROM (SELECT SUM(G.VLRDESDOB) AS VLR,
                 P.NOMEPARC || ': R$ ' || ROUND(SUM(G.VLRDESDOB)) || ' em 12m' AS TXT
            FROM GASTO G JOIN TGFPAR P ON P.CODPARC = G.CODPARC
           GROUP BY P.NOMEPARC
           ORDER BY SUM(G.VLRDESDOB) DESC FETCH FIRST 8 ROWS ONLY) X
)
SELECT A.VLR_TRIMESTRE, A.VLR_12M, A.VLR_TRIM_ANO_PASSADO, A.FORNECEDORES, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
