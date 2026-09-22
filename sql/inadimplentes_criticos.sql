-- KPI: inadimplentes_criticos
-- Pergunta: quem são os grandes devedores, e por que ainda estão comprando?
--
-- Diferente de inadimplencia.sql, que mede o TOTAL vencido: aqui o alvo são
-- os nomes. A cobrança vai nominal para a gestora do financeiro, com o dado
-- que muda a conversa — SE O DEVEDOR AINDA ESTÁ COMPRANDO.
--
-- Cliente que deve há 120 dias e continua faturando é falha de bloqueio, não
-- de cobrança, e a ação é outra: travar o crédito, não ligar de novo.
--
-- Consolida por CODPARCMATRIZ quando existe: filial que deve e matriz que
-- compra são o mesmo risco. (TGFPAR.CODGRUPO está zerado na base e não serve;
-- CODPARCMATRIZ é o campo certo — 2.354 clientes têm matriz cadastrada.)
--
-- Intercompany excluído: empresa do grupo devendo a empresa do grupo não é
-- inadimplência, é conta a acertar.
--
-- Params: {{CODEMP}}  {{JANELA_VENCIDO_DIAS}}  {{DEVEDOR_PISO}}

WITH VENC AS (
  SELECT NVL(P.CODPARCMATRIZ, F.CODPARC) AS CODGRP,
         F.VLRDESDOB,
         TRUNC(SYSDATE) - TRUNC(F.DTVENC) AS DIAS_ATRASO
    FROM TGFFIN F /*CC TGFFIN CC*/
    JOIN TGFPAR P ON P.CODPARC = F.CODPARC
   WHERE F.DHBAIXA IS NULL
     AND F.RECDESP = 1
     AND NVL(F.PROVISAO,'N') = 'N'
     AND F.CODEMP IN ({{CODEMP}})
     AND F.DTVENC <  TRUNC(SYSDATE)
     AND F.DTVENC >= TRUNC(SYSDATE) - {{JANELA_VENCIDO_DIAS}}
     AND F.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
),
DEVEDOR AS (
  SELECT CODGRP,
         SUM(VLRDESDOB) AS VLR,
         MAX(DIAS_ATRASO) AS PIOR_ATRASO,
         COUNT(*) AS TITULOS
    FROM VENC GROUP BY CODGRP
  HAVING SUM(VLRDESDOB) >= {{DEVEDOR_PISO}}
),
COMPRANDO AS (
  -- Faturamento dos últimos 30 dias por grupo de parceiro.
  SELECT NVL(P.CODPARCMATRIZ, C.CODPARC) AS CODGRP, SUM(C.VLRNOTA) AS VLR_30D
    FROM TGFCAB C
    JOIN TGFPAR P ON P.CODPARC = C.CODPARC
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TGFTOP
                           WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S')
     AND C.CODEMP IN ({{CODEMP}})
     AND C.DTNEG >= TRUNC(SYSDATE) - 30
   GROUP BY NVL(P.CODPARCMATRIZ, C.CODPARC)
),
AGG AS (
  SELECT COUNT(*) AS DEVEDORES_ACIMA_PISO,
         ROUND(NVL(SUM(D.VLR),0),2) AS VLR_CONCENTRADO,
         NVL(MAX(D.PIOR_ATRASO),0) AS PIOR_ATRASO,
         SUM(CASE WHEN NVL(X.VLR_30D,0) > 0 THEN 1 ELSE 0 END) AS AINDA_COMPRANDO,
         ROUND(NVL(SUM(CASE WHEN NVL(X.VLR_30D,0) > 0 THEN X.VLR_30D END),0),2)
           AS VLR_FATURADO_A_DEVEDOR
    FROM DEVEDOR D LEFT JOIN COMPRANDO X ON X.CODGRP = D.CODGRP
),
TOPO AS (
  SELECT LISTAGG(Y.TXT, ' · ') WITHIN GROUP (ORDER BY Y.VLR DESC) AS LISTA
    FROM (SELECT D.VLR,
                 P.NOMEPARC || ' — R$ ' || ROUND(D.VLR) || ' (' || D.PIOR_ATRASO
                   || 'd' || CASE WHEN NVL(X.VLR_30D,0) > 0
                                  THEN ', AINDA COMPRANDO R$ ' || ROUND(X.VLR_30D)
                                  ELSE '' END || ')' AS TXT
            FROM DEVEDOR D
            JOIN TGFPAR P ON P.CODPARC = D.CODGRP
            LEFT JOIN COMPRANDO X ON X.CODGRP = D.CODGRP
           ORDER BY D.VLR DESC FETCH FIRST 10 ROWS ONLY) Y
)
SELECT A.DEVEDORES_ACIMA_PISO, A.VLR_CONCENTRADO, A.PIOR_ATRASO,
       A.AINDA_COMPRANDO, A.VLR_FATURADO_A_DEVEDOR, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
