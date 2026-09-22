-- KPI: gastos_acima_media
-- Pergunta: qual natureza de despesa estourou o próprio padrão no mês passado?
--
-- ESCOPO: só as naturezas que Compras decide — grupo 3 (matéria-prima,
-- embalagens, injeção terceirizada, etiquetas, materiais para revenda) mais
-- 8010700 (adiantamento a fornecedores). Empréstimos, dividendos, folha,
-- impostos e aluguel ficam com o financeiro em gastos_financeiros.sql:
-- cobrar Compras por Empréstimos e Financiamentos seria cobrança sem alçada,
-- e é justamente a natureza que mais estourou no mês (+265%).
--
-- Compara cada natureza consigo mesma, e não contra o faturamento, de
-- propósito: a razão despesa/faturamento passa de 190% porque mistura
-- matéria-prima com empréstimo, e não é interpretável como percentual de
-- gasto. Esse recorte está em despesa_sobre_faturamento.sql, em sombra por
-- isso.
--
-- Piso de relevância {{GASTO_PISO_MES}}: sem ele, natureza de R$ 300/mês que
-- virou R$ 900 aparece como "+200%" e enterra o alerta que importa.
--
-- Aferido 22/09/2026 — as naturezas de compra e sua média mensal de 12 meses:
--   3010101 Matéria Prima                     R$ 2.237.376
--   3010105 Injeção Terceirizada              R$   358.192   (ago/26: +87%)
--   8010700 Adiantamento a Fornecedores       R$   387.682   (ago/26: +40%)
--   3010106 Etiquetas e Acessórios            R$   175.477
--   3010103 Embalagens                        R$   172.855   (ago/26: +83%)
--   3010107 Materiais Nacionais para Revenda  R$   166.902
--
-- Params: {{CODEMP}}  {{GASTO_PISO_MES}}  {{GASTO_ESTOURO_PCT}}  {{NAT_COMPRAS}}

WITH DESP AS (
  SELECT F.CODNAT, F.DTNEG, F.VLRDESDOB
    FROM TGFFIN F /*CC TGFFIN CC*/
   WHERE F.CODEMP IN ({{CODEMP}})
     AND F.RECDESP = -1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.CODNAT IN ({{NAT_COMPRAS}})
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
