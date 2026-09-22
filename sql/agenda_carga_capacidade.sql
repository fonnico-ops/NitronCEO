-- KPI: agenda_carga_capacidade
-- Pergunta: a agenda de carga cabe na capacidade de {{META_DIA}} por dia?
--
-- A REGRA DE NEGÓCIO: a operação carrega e fatura cerca de R$ 500 mil por dia
-- útil nas empresas 1, 2, 4 e 14. Data agendada acima disso não é ambição —
-- é ficção: o caminhão não sai, o pedido não fatura, e o dia seguinte herda a
-- sobra. Data muito abaixo é doca ociosa no mesmo dia em que outra data
-- estoura.
--
-- FONTE: TGFORD.DTPREVSAIDA (data prevista de saída da ordem de carga) com o
-- valor dos pedidos amarrados à ordem. É o agendamento de carga de verdade —
-- AD_TSIAGENENT é o acordo com o CLIENTE, que é outra coisa e está quase
-- sempre vazio (96% da carteira sem data).
--
-- O valor vem por subquery escalar por ordem, não por join: juntar TGFORD a
-- TGFCAB e somar VLRNOTA multiplicaria o valor da nota por ordem repetida.
--
-- APURADO EM 22/09/2026 — a agenda das duas semanas seguintes:
--   10/09  R$ 1.886.942   <- 3,8x a capacidade
--   02/10  R$ 1.875.158   <- 3,8x, em 28 ordens TODAS ABERTAS
--   22/09  R$   840.451   <- 1,7x
--   17/09  R$   635.845     21/09  R$ 604.246     09/09  R$ 569.107
--   ...e no mesmo período:
--   24/09  R$   151.456     25/09  R$ 154.165
--   29/09  R$    37.728     30/09  R$  79.457
--   E 58 ordens ainda ABERTAS com data prevista vencida há mais de 30 dias:
--   carga que nunca saiu e ninguém fechou. Sai em ORDENS_ABANDONADAS.
--   (As 26.632 ordens FECHADAS com data vencida são histórico normal e NÃO
--   entram — contá-las foi o primeiro erro desta query.)
--
-- Resultado em 22/09/2026: 11 dias agendados nos próximos 15 úteis,
--   2 estourados, 9 OCIOSOS, R$ 1.715.609,62 a remanejar e R$ 3.512.518,91
--   de capacidade parada. O problema não é falta de carga — é distribuição.
--
-- A métrica é VLR_A_REMANEJAR — quanto precisa sair das datas que estouram.
-- Contar dias fora da faixa não diz o tamanho do problema; o valor diz.
--
-- Params: {{CODEMP_META}}  {{META_DIA}}  {{AGENDA_DIAS}}

WITH CARGA AS (
  SELECT O.CODEMP, O.ORDEMCARGA, O.DTPREVSAIDA, O.SITUACAO,
         (SELECT NVL(SUM(C.VLRNOTA),0) FROM TGFCAB C
           WHERE C.ORDEMCARGA = O.ORDEMCARGA AND C.CODEMP = O.CODEMP) AS VLR
    FROM TGFORD O /*CC TGFORD CC*/
   WHERE O.CODEMP IN ({{CODEMP_META}})
     AND O.DTPREVSAIDA IS NOT NULL
),
POR_DIA AS (
  SELECT DTPREVSAIDA AS DIA, SUM(VLR) AS VLR, COUNT(*) AS ORDENS,
         SUM(CASE WHEN SITUACAO = 'A' THEN 1 ELSE 0 END) AS ABERTAS
    FROM CARGA
   WHERE DTPREVSAIDA >= TRUNC(SYSDATE)
     AND DTPREVSAIDA <  TRUNC(SYSDATE) + {{AGENDA_DIAS}}
     AND TO_CHAR(DTPREVSAIDA,'DY','NLS_DATE_LANGUAGE=ENGLISH')
           NOT IN ('SAT','SUN')
   GROUP BY DTPREVSAIDA
),
AGG AS (
  SELECT
    COUNT(*)                                                       AS DIAS_AGENDADOS,
    SUM(CASE WHEN VLR > {{META_DIA}} THEN 1 ELSE 0 END)            AS DIAS_ESTOURADOS,
    SUM(CASE WHEN VLR < {{META_DIA}} * 0.6 THEN 1 ELSE 0 END)      AS DIAS_OCIOSOS,
    ROUND(NVL(SUM(CASE WHEN VLR > {{META_DIA}}
                       THEN VLR - {{META_DIA}} END),0),2)          AS VLR_A_REMANEJAR,
    ROUND(NVL(SUM(CASE WHEN VLR < {{META_DIA}} * 0.6
                       THEN {{META_DIA}} - VLR END),0),2)          AS VLR_OCIOSO,
    ROUND(NVL(SUM(VLR),0),2)                                       AS VLR_AGENDADO_TOTAL
  FROM POR_DIA
),
SUJEIRA AS (
  -- Ordem ABERTA cuja data prevista já passou faz tempo: carga que nunca
  -- saiu e ninguém fechou. Só as abertas entram — 26.632 ordens FECHADAS
  -- têm data vencida, e isso é histórico normal, não sujeira.
  SELECT COUNT(*) AS ORDENS_ABANDONADAS FROM CARGA
   WHERE SITUACAO = 'A' AND DTPREVSAIDA < TRUNC(SYSDATE) - 30
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.DIA) AS LISTA
    FROM (SELECT D.DIA,
                 TO_CHAR(D.DIA,'DD/MM') || ': R$ ' || ROUND(D.VLR)
                   || CASE WHEN D.VLR > {{META_DIA}}
                           THEN ' (' || ROUND(D.VLR/{{META_DIA}},1) || 'x a capacidade, '
                                || D.ABERTAS || ' ordens abertas)'
                           ELSE ' (dia ocioso)' END AS TXT
            FROM POR_DIA D
           WHERE D.VLR > {{META_DIA}} OR D.VLR < {{META_DIA}} * 0.6
           ORDER BY D.DIA FETCH FIRST 12 ROWS ONLY) X
)
SELECT A.DIAS_AGENDADOS, A.DIAS_ESTOURADOS, A.DIAS_OCIOSOS,
       A.VLR_A_REMANEJAR, A.VLR_OCIOSO, A.VLR_AGENDADO_TOTAL,
       S.ORDENS_ABANDONADAS, T.LISTA
  FROM AGG A CROSS JOIN SUJEIRA S CROSS JOIN TOPO T
