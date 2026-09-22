-- KPI: liberacao_comercial
-- Pergunta: quantos pedidos esperam aprovação ou recusa do comercial?
--
-- Mesma fila do TSILIB, outros eventos — os que NÃO são decisão de crédito:
--    9 Tempo Inativo | 1004 PIX - Aguardando Recebimento
--   13 Valor Mínimo Tipo Negoc. | 44 Liberação exigida pela TOP
--   12 Frete CIF | 18 Confirmação de Nota
--
-- Aferido 22/09/2026 (180 dias): 87 pedidos travados, R$ 505.694,43
--    evento    9 Tempo Inativo        42 pedidos  R$ 264.488,21  até 139 dias
--    evento 1004 PIX Aguard. Receb.   34 pedidos  R$ 185.710,07  até 180 dias
--    evento   13 Valor Mínimo          4 pedidos  R$   7.190,47  até  67 dias
--    evento   44 Liberação pela TOP    3 pedidos  R$  39.654,78  até  67 dias
--
-- 180 dias parado não é fila — é pedido que ninguém decidiu recusar. A ação
-- deste KPI pede as duas saídas explicitamente: libera ou recusa. Deixar
-- envelhecer não é uma terceira opção, mas é o que está acontecendo.
--
-- Params: {{CODEMP}}  {{LIBERACAO_DIAS}}  {{EVENTOS_CREDITO}}

WITH FILA AS (
  SELECT L.NUCHAVE, L.EVENTO, L.DHSOLICIT,
         TRUNC(SYSDATE) - TRUNC(L.DHSOLICIT) AS DIAS,
         NVL(C.VLRNOTA,0) AS VLRNOTA, C.CODPARC
    FROM TSILIB L /*CC TSILIB CC*/
    LEFT JOIN TGFCAB C ON C.NUNOTA = L.NUCHAVE AND C.CODEMP IN ({{CODEMP}})
   WHERE L.TABELA = 'TGFCAB'
     AND L.DHLIB IS NULL
     AND NVL(L.REPROVADO,'N') = 'N'
     AND L.EVENTO NOT IN ({{EVENTOS_CREDITO}})
     AND L.DHSOLICIT >= TRUNC(SYSDATE) - {{LIBERACAO_DIAS}}
),
AGG AS (
  SELECT COUNT(*) AS PEDIDOS_TRAVADOS,
         ROUND(NVL(SUM(VLRNOTA),0),2) AS VLR_TRAVADO,
         NVL(MAX(DIAS),0) AS DIAS_MAX,
         ROUND(NVL(AVG(DIAS),0),1) AS DIAS_MEDIO,
         SUM(CASE WHEN DIAS > 30 THEN 1 ELSE 0 END) AS PARADOS_MAIS_30D
    FROM FILA
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ', ') WITHIN GROUP (ORDER BY X.DIAS DESC) AS LISTA
    FROM (SELECT F.DIAS,
                 NVL(P.NOMEPARC,'?') || ' — R$ ' || ROUND(F.VLRNOTA)
                   || ' (' || F.DIAS || 'd, ' || NVL(E.DESCRICAO,'?') || ')' AS TXT
            FROM FILA F
            LEFT JOIN TGFPAR P ON P.CODPARC = F.CODPARC
            LEFT JOIN VGFLIBEVE E ON E.EVENTO = F.EVENTO
           ORDER BY F.DIAS DESC FETCH FIRST 10 ROWS ONLY) X
)
SELECT A.PEDIDOS_TRAVADOS, A.VLR_TRAVADO, A.DIAS_MAX, A.DIAS_MEDIO,
       A.PARADOS_MAIS_30D, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
