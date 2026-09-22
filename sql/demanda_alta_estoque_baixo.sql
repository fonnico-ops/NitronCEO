-- KPI: demanda_alta_estoque_baixo
-- Pergunta: o que o PCP tem que colocar na programação esta semana?
--
-- Cruza as duas pontas: produtos no topo da demanda (por VALOR vendido nos
-- últimos 90 dias) que estão com cobertura curta. É a lista de programação,
-- não um alerta genérico de estoque — por isso o corte é de RELEVÂNCIA
-- (>= {{DEMANDA_PISO_MES}} por mês) e não de quantidade de itens.
--
-- A diferença para cobertura_estoque.sql: lá o alerta é "quantos produtos vão
-- acabar"; aqui é "destes, quais valem programar primeiro". Um produto de
-- R$ 200/mês com 3 dias de cobertura é ruído para o PCP; um de R$ 80 mil/mês
-- com 5 dias é a pauta da reunião.
--
-- Mesmas regras de saldo e de TOP do cobertura_estoque.sql.
--
-- Params: {{CODEMP}}  {{CODEMP_SALDO}}  {{LOCAL_TRANSFERENCIA}}
--         {{COBERTURA_ALERTA_DIAS}}  {{DEMANDA_PISO_MES}}

WITH TOPQTD AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND ATUALEST = 'B' AND NVL(AD_INSEREDASH,'N') = 'S'
),
CONSUMO AS (
  SELECT I.CODPROD,
         SUM(I.QTDNEG)/90 AS QTD_DIA,
         SUM(I.VLRTOT - NVL(I.VLRDESC,0))/90 AS VLR_DIA
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPQTD)
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 90
   GROUP BY I.CODPROD
  HAVING SUM(I.QTDNEG) > 0
     AND SUM(I.VLRTOT - NVL(I.VLRDESC,0))/3 >= {{DEMANDA_PISO_MES}}
),
SALDO AS (
  SELECT CODPROD, SUM(NVL(ESTOQUE,0)) AS FISICO
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}})
     AND CODLOCAL <> {{LOCAL_TRANSFERENCIA}}
     AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
),
CRITICO AS (
  SELECT C.CODPROD, C.VLR_DIA, NVL(S.FISICO,0) AS FISICO,
         NVL(S.FISICO,0) / C.QTD_DIA AS DIAS_COB
    FROM CONSUMO C LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
   WHERE NVL(S.FISICO,0) / C.QTD_DIA < {{COBERTURA_ALERTA_DIAS}}
),
AGG AS (
  SELECT COUNT(*) AS ITENS_PARA_PROGRAMAR,
         ROUND(NVL(SUM(VLR_DIA * 30),0),2) AS VLR_MES_EXPOSTO,
         SUM(CASE WHEN FISICO <= 0 THEN 1 ELSE 0 END) AS ITENS_SEM_SALDO
    FROM CRITICO
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ', ') WITHIN GROUP (ORDER BY X.VLR_DIA DESC) AS LISTA
    FROM (SELECT C.VLR_DIA,
                 P.DESCRPROD || ' — R$ ' || ROUND(C.VLR_DIA*30) || '/mês, '
                   || CASE WHEN C.FISICO <= 0 THEN 'SEM SALDO'
                           ELSE ROUND(C.DIAS_COB,1) || 'd de cobertura'
                      END AS TXT
            FROM CRITICO C JOIN TGFPRO P ON P.CODPROD = C.CODPROD
           ORDER BY C.VLR_DIA DESC FETCH FIRST 15 ROWS ONLY) X
)
SELECT A.ITENS_PARA_PROGRAMAR, A.VLR_MES_EXPOSTO, A.ITENS_SEM_SALDO, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
