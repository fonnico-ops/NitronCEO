-- KPI: cobertura_estoque
-- Pergunta: quantos produtos vão acabar antes de a produção repor?
--
-- POR QUE NÃO USA ESTMIN: TGFEST.ESTMIN está 100% ZERADO em todas as empresas
-- (conferido em 2, 4 e 14 — 31.631 linhas, nenhuma com mínimo). O estoque
-- mínimo do cadastro não existe na prática, então "pouco estoque" tem que ser
-- derivado do giro.
--
-- COBERTURA = saldo físico / venda média diária dos últimos 90 dias.
-- É melhor que o mínimo de cadastro: o mínimo é estático e envelhece; a
-- cobertura acompanha a sazonalidade sozinha.
--
-- SALDO: exclui CODLOCAL {{LOCAL_TRANSFERENCIA}} ("Estoque para
-- Transferência"), que é conta de contrapartida e fica negativa por
-- construção — ver o cabeçalho de ruptura_estoque.sql. Sem esse filtro,
-- 653 dos 891 produtos com giro apareciam sem saldo; com ele, 129.
--
-- VENDA: ATUALCOM='C' + ATUALEST='B'. O ATUALEST='B' é obrigatório aqui —
-- esta é análise de QUANTIDADE, e sem ele a TOP 3110 infla o volume em ~21%.
--
-- Aferido 22/09/2026: 891 produtos com giro | 129 com cobertura < 7 dias |
-- 138 < 15 dias | 153 < 30 dias | R$ 455.469,99 de venda mensal em risco.
--
--
-- PRODUTO SUSPENSO NÃO ENTRA. TGFPRO.AD_AG_SUSPENSO='S' marca 652 produtos
-- que saíram de linha ou estão bloqueados. Mandar o PCP produzir um item
-- suspenso é pedir trabalho que será jogado fora.
-- Nulo (1.332 produtos) conta como NÃO suspenso: na dúvida, o item aparece.
-- Efeito medido em 22/09/26 na ruptura: 92 itens sem saldo caem para 28 —
-- 64 eram suspensos. O valor quase não muda (R$ 287.768 -> R$ 282.134),
-- porque os suspensos são cauda longa; o que muda é a lista que o PCP
-- recebe, que deixa de vir com 64 itens que ele não deve produzir.
--
-- Params: {{CODEMP}}  {{CODEMP_SALDO}}  {{LOCAL_TRANSFERENCIA}}
--         {{COBERTURA_ALERTA_DIAS}}

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
    JOIN TGFPRO P ON P.CODPROD = I.CODPROD
   WHERE NVL(P.AD_AG_SUSPENSO,'N') <> 'S'
     AND C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPQTD)
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 90
   GROUP BY I.CODPROD
  HAVING SUM(I.QTDNEG) > 0
),
SALDO AS (
  SELECT CODPROD, SUM(NVL(ESTOQUE,0)) AS FISICO
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}})
     AND CODLOCAL <> {{LOCAL_TRANSFERENCIA}}
     AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
),
COB AS (
  SELECT C.CODPROD, C.QTD_DIA, C.VLR_DIA, NVL(S.FISICO,0) AS FISICO,
         NVL(S.FISICO,0) / C.QTD_DIA AS DIAS_COB
    FROM CONSUMO C LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
),
AGG AS (
  SELECT COUNT(*) AS PRODUTOS_COM_GIRO,
         SUM(CASE WHEN DIAS_COB < 7  THEN 1 ELSE 0 END) AS COB_MENOR_7D,
         SUM(CASE WHEN DIAS_COB < {{COBERTURA_ALERTA_DIAS}} THEN 1 ELSE 0 END)
           AS COB_ABAIXO_ALERTA,
         SUM(CASE WHEN FISICO <= 0 THEN 1 ELSE 0 END) AS SALDO_NAO_POSITIVO,
         ROUND(SUM(CASE WHEN DIAS_COB < {{COBERTURA_ALERTA_DIAS}}
                        THEN VLR_DIA * 30 ELSE 0 END), 2) AS VLR_MES_EM_RISCO
    FROM COB
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ', ') WITHIN GROUP (ORDER BY X.VLR_DIA DESC) AS LISTA
    FROM (SELECT C.VLR_DIA,
                 P.DESCRPROD || ' ('
                   || CASE WHEN C.FISICO <= 0 THEN 'sem saldo'
                           ELSE ROUND(C.DIAS_COB,1) || 'd' END || ')' AS TXT
            FROM COB C JOIN TGFPRO P ON P.CODPROD = C.CODPROD
           WHERE C.DIAS_COB < {{COBERTURA_ALERTA_DIAS}}
           ORDER BY C.VLR_DIA DESC FETCH FIRST 12 ROWS ONLY) X
)
SELECT A.PRODUTOS_COM_GIRO, A.COB_MENOR_7D, A.COB_ABAIXO_ALERTA,
       A.SALDO_NAO_POSITIVO, A.VLR_MES_EM_RISCO, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
