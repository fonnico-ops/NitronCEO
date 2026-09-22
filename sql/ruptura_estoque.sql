-- KPI: ruptura_estoque
-- Pergunta: quanto de venda está parada esperando o PCP produzir?
--
-- DEMANDA: carteira roteirizável, na definição da skill de roteirização —
--   TIPMOV='P', STATUSNOTA='L', PENDENTE='S', sem ordem de carga, com corte
--   temporal (há ~27 mil pedidos pendentes desde 2020; sem o corte a análise
--   vira arqueologia).
--
-- SALDO — A CORREÇÃO QUE MUDA TUDO (apurada em 22/09/2026):
--   `CODLOCAL = 1080000` ("Estoque para Transferência") é conta de
--   CONTRAPARTIDA e fica negativa por construção. Somá-la destrói o saldo:
--     PA DE LIXO COM CABO (268), saldo por local na empresa 2:
--       CODLOCAL 1080000 "Estoque p/ Transferência"  -158.364  <- contrapartida
--       CODLOCAL 2990314 "Preparação 14"              +21.444
--       CODLOCAL 2071101 "G1101"                       +3.696
--       (demais endereços)                            ...
--     Somando tudo: -123.641 unidades (absurdo, o item é campeão de venda).
--     Excluindo a 1080000:  +28.241 unidades (real).
--   A primeira versão deste KPI somava a 1080000 e acusava 460 itens em
--   ruptura. Com o filtro correto o número cai para a casa das dezenas.
--
--   Ainda restam endereços físicos com saldo negativo (ex.: H1401 -19.248).
--   Esses são inconsistência real de endereçamento, e NÃO são escondidos
--   aqui: entram na soma (deprimindo o saldo) e são contados em
--   ENDERECOS_NEGATIVOS, que é sinal para o WMS, não para o PCP.
--
-- CODEMP 1 continua fora da fonte de saldo: 12,5 milhões de linhas somando
-- 3×10^19 unidades — dado histórico corrompido.
--
-- Params: {{CODEMP}}  {{CODEMP_SALDO}}  {{CARTEIRA_DIAS}}  {{LOCAL_TRANSFERENCIA}}

WITH CARTEIRA AS (
  SELECT I.CODPROD,
         SUM(I.QTDNEG) AS QTD_PEDIDA,
         SUM(I.VLRTOT - NVL(I.VLRDESC,0)) AS VLR
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.TIPMOV = 'P'
     AND C.STATUSNOTA = 'L'
     AND NVL(C.PENDENTE,'N') = 'S'
     AND NVL(C.ORDEMCARGA,0) = 0
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - {{CARTEIRA_DIAS}}
   GROUP BY I.CODPROD
),
SALDO AS (
  -- Saldo físico, não ESTOQUE-RESERVADO: RESERVADO já contém os pedidos
  -- pendentes que estamos avaliando, e subtrair duas vezes manda pedido bom
  -- para a fila de ruptura.
  SELECT CODPROD,
         SUM(NVL(ESTOQUE,0)) AS FISICO,
         SUM(CASE WHEN ESTOQUE < 0 THEN 1 ELSE 0 END) AS ENDERECOS_NEG
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}})
     AND CODLOCAL <> {{LOCAL_TRANSFERENCIA}}
     AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
)
SELECT
  (SELECT COUNT(*) FROM CARTEIRA)                                    AS ITENS_CARTEIRA,
  (SELECT COUNT(*) FROM CARTEIRA C LEFT JOIN SALDO S ON S.CODPROD=C.CODPROD
    WHERE NVL(S.FISICO,0) <= 0)                                      AS ITENS_SEM_SALDO,
  (SELECT COUNT(*) FROM CARTEIRA C LEFT JOIN SALDO S ON S.CODPROD=C.CODPROD
    WHERE NVL(S.FISICO,0) > 0 AND NVL(S.FISICO,0) < C.QTD_PEDIDA)    AS ITENS_SALDO_PARCIAL,
  (SELECT ROUND(NVL(SUM(C.VLR),0),2) FROM CARTEIRA C
     LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
    WHERE NVL(S.FISICO,0) < C.QTD_PEDIDA)                            AS VLR_EM_RISCO,
  (SELECT NVL(SUM(S.ENDERECOS_NEG),0) FROM CARTEIRA C
     JOIN SALDO S ON S.CODPROD = C.CODPROD)                          AS ENDERECOS_NEGATIVOS,
  (SELECT LISTAGG(P.DESCRPROD || ' (R$ ' || ROUND(X.VLR) || ')', ', ')
          WITHIN GROUP (ORDER BY X.VLR DESC)
     FROM (SELECT C.CODPROD, C.VLR FROM CARTEIRA C
             LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
            WHERE NVL(S.FISICO,0) <= 0
            ORDER BY C.VLR DESC FETCH FIRST 10 ROWS ONLY) X
     JOIN TGFPRO P ON P.CODPROD = X.CODPROD)                         AS LISTA
FROM DUAL
