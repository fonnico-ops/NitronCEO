-- KPI: ordens_servico_abertas
-- Pergunta: quantas ordens de serviço estão abertas, e há quanto tempo?
--
-- FONTE: AD_TGFMANUT — a ordem de serviço de manutenção. Viva: 12.310 OS,
-- a última aberta em 22/09/2026. Aberta = TERMSERV IS NULL; tempo de
-- fechamento = TERMSERV - DHOS.
--
-- COMO O BACKLOG SE DISTRIBUI (22/09/2026, 503 OS abertas):
--
--   TIPO         abertas   idade mediana   mais de 180d   equip. parado
--   INDUSTRIAL     222         133 dias          71            184
--   PREDIAL        168         171 dias          77            108
--   MOLDES         108          93 dias          13             34
--   GEN              5          22 dias           1              4
--   A mais antiga tem 602 dias. Só 7 das 503 têm menos de uma semana.
--
-- TEMPO DE FECHAMENTO das que fecharam (últimos 365 dias) — a mediana é boa
-- e a cauda é o problema:
--   MOLDES      1.295 fechadas   mediana 0,7 dia   72 levaram mais de 30 dias
--   INDUSTRIAL    291            mediana 1,8 dia   20 acima de 30 dias
--   PREDIAL       175            mediana 4,4 dias  33 acima de 30 dias
--   GEN            43            mediana 13,1 dias 15 acima de 30 dias
--
-- A LEITURA HONESTA: 330 OS abertas dizem que o equipamento está PARADO,
-- algumas há mais de um ano. É implausível que 330 equipamentos estejam
-- parados há meses. O número quase certamente mistura serviço realmente
-- pendente com OS que foi executada e nunca fechada no sistema. Os dois são
-- problema — um de manutenção, outro de disciplina — e a ação pede que sejam
-- separados antes de qualquer outra coisa. É o mesmo padrão das ordens de
-- carga abandonadas (ver agenda_carga_capacidade.sql).
--
-- CAMPOS QUE NÃO SERVEM PARA AGRUPAR:
--   LOCAL é texto livre e tem 5 grafias de "ferramentaria" (FERRAMENTARIA,
--   ferramentaria, Ferramentaria, FERRAMEMTARIA, "FERRAMENTARIA ."). Só
--   entra normalizado em maiúsculas, e ainda assim com ressalva.
--   PRIORIDADE perdeu sentido: 10.460 das 12.310 OS (85%) estão URGENTE.
--   Quando tudo é urgente, nada é — por isso a métrica não usa prioridade.
--
-- Params: {{OS_IDADE_ALERTA}}

WITH OS AS (
  SELECT NVL(TIPO,'(sem tipo)') AS TIPO,
         NVL(TIPOMANUT,'(sem classe)') AS TIPOMANUT,
         NVL(PARADO,'?') AS PARADO,
         TRUNC(SYSDATE) - TRUNC(DHOS) AS IDADE,
         UPPER(TRIM(LOCAL)) AS LOCAL_NORM
    FROM AD_TGFMANUT /*CC AD_TGFMANUT CC*/
   WHERE TERMSERV IS NULL
     AND DHOS IS NOT NULL
),
AGG AS (
  SELECT
    COUNT(*)                                                      AS ABERTAS,
    SUM(CASE WHEN IDADE > {{OS_IDADE_ALERTA}} THEN 1 ELSE 0 END)  AS ABERTAS_VELHAS,
    SUM(CASE WHEN IDADE > 180 THEN 1 ELSE 0 END)                  AS ABERTAS_ACIMA_180D,
    SUM(CASE WHEN PARADO = 'SIM' THEN 1 ELSE 0 END)               AS COM_EQPTO_PARADO,
    ROUND(MEDIAN(IDADE))                                          AS IDADE_MEDIANA,
    MAX(IDADE)                                                    AS IDADE_MAX,
    SUM(CASE WHEN TIPOMANUT = 'PREVENTIVA' THEN 1 ELSE 0 END)     AS PREVENTIVAS
  FROM OS
),
POR_TIPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.N DESC) AS LISTA
    FROM (SELECT COUNT(*) AS N,
                 TIPO || ': ' || COUNT(*) || ' abertas, mediana '
                   || ROUND(MEDIAN(IDADE)) || 'd, '
                   || SUM(CASE WHEN PARADO = 'SIM' THEN 1 ELSE 0 END)
                   || ' com equipamento parado' AS TXT
            FROM OS GROUP BY TIPO) X
),
FECHAMENTO AS (
  -- Tempo de fechamento das que fecharam, para contraste com o backlog.
  SELECT ROUND(MEDIAN(TERMSERV - DHOS),1) AS MEDIANA_FECHAMENTO,
         COUNT(*) AS FECHADAS_365D,
         SUM(CASE WHEN TERMSERV - DHOS > 30 THEN 1 ELSE 0 END) AS FECHADAS_ACIMA_30D
    FROM AD_TGFMANUT
   WHERE TERMSERV IS NOT NULL
     AND DHOS >= TRUNC(SYSDATE) - 365
     AND TERMSERV >= DHOS
)
SELECT A.ABERTAS, A.ABERTAS_VELHAS, A.ABERTAS_ACIMA_180D, A.COM_EQPTO_PARADO,
       A.IDADE_MEDIANA, A.IDADE_MAX, A.PREVENTIVAS,
       F.FECHADAS_365D, F.MEDIANA_FECHAMENTO, F.FECHADAS_ACIMA_30D, T.LISTA
  FROM AGG A CROSS JOIN FECHAMENTO F CROSS JOIN POR_TIPO T
