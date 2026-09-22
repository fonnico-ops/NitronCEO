-- KPI: gastos_acima_media
-- Pergunta: qual natureza de despesa estourou o próprio padrão no mês passado?
--
-- Compara cada CODNAT de despesa no mês fechado contra a própria média dos 12
-- meses anteriores. Compara natureza consigo mesma, e não contra o
-- faturamento, de propósito: a base de despesa da Nitron inclui matéria-prima,
-- empréstimos, dividendos e impostos, então a razão despesa/faturamento
-- passa de 190% e não é interpretável como percentual de gasto. Esse recorte
-- está em despesa_sobre_faturamento.sql, e nasce em sombra por isso.
--
-- Piso de relevância {{GASTO_PISO_MES}}: sem ele, natureza de R$ 300/mês que
-- virou R$ 900 aparece como "+200%" e enterra o alerta que importa.
--
-- Aferido 22/09/2026 — naturezas com média mensal acima de R$ 250 mil:
--   Empréstimos e Financiamentos   média R$ 2.153.038  |  ago/26 R$ 4.678.713  (+117%)
--   Matéria Prima                  média R$ 2.080.213  |  ago/26 R$ 1.903.854  (-8%)
--   Fretes e transportes NTR       média R$   659.634  |  ago/26 R$   842.709  (+28%)
--   Lucros e Dividendos            média R$   607.168  |  ago/26 R$   796.226  (+31%)
--   INSS                           média R$   457.237  |  ago/26 R$   325.603  (-29%)
--   Injeção Terceirizada           média R$   336.328  |  ago/26 R$   578.940  (+72%)
--
-- Params: {{CODEMP}}  {{GASTO_PISO_MES}}  {{GASTO_ESTOURO_PCT}}

WITH DESP AS (
  SELECT F.CODNAT, F.DTNEG, F.VLRDESDOB
    FROM TGFFIN F /*CC TGFFIN CC*/
   WHERE F.CODEMP IN ({{CODEMP}})
     AND F.RECDESP = -1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-13)
     AND F.DTNEG <  TRUNC(SYSDATE,'MM')
),
POR_NAT AS (
  SELECT CODNAT,
         SUM(CASE WHEN DTNEG <  ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
                  THEN VLRDESDOB ELSE 0 END)/12 AS MEDIA_MES,
         SUM(CASE WHEN DTNEG >= ADD_MONTHS(TRUNC(SYSDATE,'MM'),-1)
                  THEN VLRDESDOB ELSE 0 END) AS MES_FECHADO
    FROM DESP GROUP BY CODNAT
),
ESTOURO AS (
  SELECT P.CODNAT, P.MEDIA_MES, P.MES_FECHADO,
         P.MES_FECHADO / NULLIF(P.MEDIA_MES,0) * 100 AS PCT
    FROM POR_NAT P
   WHERE P.MEDIA_MES >= {{GASTO_PISO_MES}}
     AND P.MES_FECHADO > P.MEDIA_MES * {{GASTO_ESTOURO_PCT}}/100
),
AGG AS (
  SELECT COUNT(*) AS NATUREZAS_ESTOURADAS,
         ROUND(NVL(SUM(MES_FECHADO - MEDIA_MES),0),2) AS EXCESSO_TOTAL,
         ROUND(NVL(MAX(PCT),0),1) AS MAIOR_ESTOURO_PCT
    FROM ESTOURO
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.EXCESSO DESC) AS LISTA
    FROM (SELECT E.MES_FECHADO - E.MEDIA_MES AS EXCESSO,
                 N.DESCRNAT || ': R$ ' || ROUND(E.MES_FECHADO) || ' vs média R$ '
                   || ROUND(E.MEDIA_MES) || ' (' || ROUND(E.PCT) || '%)' AS TXT
            FROM ESTOURO E JOIN TGFNAT N ON N.CODNAT = E.CODNAT
           ORDER BY E.MES_FECHADO - E.MEDIA_MES DESC FETCH FIRST 10 ROWS ONLY) X
)
SELECT A.NATUREZAS_ESTOURADAS, A.EXCESSO_TOTAL, A.MAIOR_ESTOURO_PCT, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
