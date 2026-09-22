-- KPI: liberacao_credito
-- Pergunta: quantos pedidos estão travados esperando decisão de crédito?
--
-- TSILIB é a fila de liberação do Sankhya. Pendente = DHLIB IS NULL e
-- REPROVADO='N'. Quem já foi reprovado saiu da fila (virou recusa), quem foi
-- liberado tem DHLIB — só o que está nos dois nulos é decisão não tomada.
--
-- Eventos de CRÉDITO (a fila da gestora do financeiro), de VGFLIBEVE:
--    3 Limite de Crédito | 15 Limite Créd. Mensal | 8 Atraso
--
-- Aferido 22/09/2026 (180 dias): 68 pedidos travados, R$ 755.488,66
--    evento  8 Atraso              29 pedidos  R$ 341.089,27  até  35 dias
--    evento 15 Limite Créd. Mensal 25 pedidos  R$ 260.468,33  até  32 dias
--    evento  3 Limite de Crédito   14 pedidos  R$ 153.931,06  até  32 dias
--
-- A métrica é DIAS_MAX, não a contagem: 30 pedidos parados há 2 dias é fila
-- normal; 1 pedido parado há 35 dias é cliente que já desistiu.
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
     AND L.EVENTO IN ({{EVENTOS_CREDITO}})
     AND L.DHSOLICIT >= TRUNC(SYSDATE) - {{LIBERACAO_DIAS}}
),
AGG AS (
  SELECT COUNT(*) AS PEDIDOS_TRAVADOS,
         ROUND(NVL(SUM(VLRNOTA),0),2) AS VLR_TRAVADO,
         NVL(MAX(DIAS),0) AS DIAS_MAX,
         ROUND(NVL(AVG(DIAS),0),1) AS DIAS_MEDIO,
         SUM(CASE WHEN DIAS > 7 THEN 1 ELSE 0 END) AS PARADOS_MAIS_7D
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
       A.PARADOS_MAIS_7D, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
