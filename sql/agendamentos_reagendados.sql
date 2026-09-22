-- KPI: agendamentos_reagendados
-- Pergunta: quantas entregas o cliente empurrou, e quem tratou?
--
-- AD_TSIAGENENT está viva (384 registros em set/26). Domínio de STATUS:
--   C Confirmado | M Mudança de Data | N Sem data | R Recusa | T Não atende
--
-- ARMADILHA: STATUS='M' aparece só 1x em set/26 — a equipe registra a mudança
-- sobrescrevendo NOVADATA em vez de marcar o status. Por isso o numerador usa
-- DOIS sinais: STATUS em (M,R,T,N) OU NOVADATA divergente da DTPREVENT do
-- pedido.
--
-- MEDIDO EM 22/09/2026 (janela 30 dias): 555 agendamentos, 94 "reagendados"
-- (16,9%), 0 recusas, 0 não-atende — MAS 456 dos 555 (82%) não têm DTPREVENT
-- no pedido. O proxy só consegue avaliar 99 casos, e 94 deles divergem. Isto é
-- perto de dizer "quase todo pedido com DTPREVENT tem NOVADATA diferente", que
-- é sobre preenchimento de cadastro, não sobre o cliente empurrar a entrega.
-- O KPI fica em sombra: o dado de reagendamento não existe de forma confiável
-- hoje. Ver docs/achados-de-dados.md.
--
-- 15 campos da tabela são CALCULADOS e não existem como coluna
-- (EMAIL, TELEFONE, M3, PESO, ORDEMCARGA1...). SELECT neles falha.
--
-- Params: {{JANELA_DIAS}}

WITH AGEND AS (
  SELECT A.NUAGENDAMETO, A.NUNOTA, A.STATUS, A.DATA, A.NOVADATA, C.DTPREVENT,
         ROW_NUMBER() OVER (PARTITION BY A.NUNOTA ORDER BY A.DATA DESC) AS RN
    FROM AD_TSIAGENENT A /*CC AD_TSIAGENENT CC*/
    LEFT JOIN TGFCAB C ON C.NUNOTA = A.NUNOTA
   WHERE A.DATA >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
),
ULT AS (SELECT * FROM AGEND WHERE RN = 1)
SELECT
  COUNT(*)                                                        AS AGENDAMENTOS,
  SUM(CASE WHEN STATUS IN ('M','R','T','N')
             OR (NOVADATA IS NOT NULL AND DTPREVENT IS NOT NULL
                 AND TRUNC(NOVADATA) <> TRUNC(DTPREVENT))
           THEN 1 ELSE 0 END)                                     AS REAGENDADOS,
  SUM(CASE WHEN STATUS = 'R' THEN 1 ELSE 0 END)                   AS RECUSAS,
  SUM(CASE WHEN STATUS = 'T' THEN 1 ELSE 0 END)                   AS NAO_ATENDE,
  ROUND(SUM(CASE WHEN STATUS IN ('M','R','T','N')
             OR (NOVADATA IS NOT NULL AND DTPREVENT IS NOT NULL
                 AND TRUNC(NOVADATA) <> TRUNC(DTPREVENT))
           THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0) * 100, 1)      AS PCT_REAGENDADO
FROM ULT
