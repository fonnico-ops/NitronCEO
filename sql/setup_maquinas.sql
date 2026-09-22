-- KPI: setup_maquinas
-- Pergunta: a troca de molde está dentro dos {{SETUP_PADRAO_MIN}} minutos?
--
-- FONTE: TPRIWC — intervalos de parada do centro de trabalho, com
-- AD_CODMTP apontando para TPRMTP (cadastro de motivos). Setup é
-- AD_CODMTP = {{MOTIVO_SETUP}} ("SETUP", MOTIVOPARADA='S').
-- A tabela está VIVA: 80.308 linhas, última gravação em 22/09/2026 18:28,
-- 3.066 paradas nos últimos 30 dias.
--
-- Isto SUBSTITUI duas tentativas anteriores, ambas ruins:
--   1. AD_PARADAMAQUINA — morreu em 31/10/2024.
--   2. Inferir setup pela lacuna entre OPs consecutivas na mesma injetora.
--      Dava mediana de 2 minutos, ou seja, não media troca de molde nenhuma.
--
-- MEDIANA, NÃO MÉDIA. Nos últimos 30 dias: 217 setups fechados, média de
-- 329,5 min e MEDIANA de 127 min. A média é distorcida por 8 paradas acima
-- de 24 horas (a maior tem 5.459 min = 91 h), que são apontamento que ficou
-- aberto atravessando turno e fim de semana, não troca de molde. A mediana
-- não se move com esses casos; a média triplica por causa deles.
--
-- Paradas acima de {{SETUP_TETO_MIN}} minutos ficam fora do cálculo e são
-- contadas à parte, porque são problema de APONTAMENTO, não de setup — e as
-- duas coisas se resolvem com gente diferente.
--
-- APURADO EM 22/09/2026 (30 dias, padrão de 40 min):
--   217 setups fechados | mediana 127 min | apenas 54 (25%) dentro do padrão
--   68 acima de 4 horas | 8 acima de 24 horas | o menor levou 5,8 min
--
-- Params: {{MOTIVO_SETUP}}  {{JANELA_DIAS}}  {{SETUP_TETO_MIN}}
--         {{SETUP_PADRAO_MIN}}

WITH PARADA AS (
  SELECT I.CODWCP,
         (I.DHFINAL - I.DHINCIAL) * 1440 AS MINUTOS
    FROM TPRIWC I /*CC TPRIWC CC*/
   WHERE I.AD_CODMTP = {{MOTIVO_SETUP}}
     AND I.DHFINAL IS NOT NULL
     AND I.DHINCIAL >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
),
VALIDA AS (
  SELECT * FROM PARADA WHERE MINUTOS > 0 AND MINUTOS <= {{SETUP_TETO_MIN}}
),
TOTAIS AS (
  -- Escalares em CTE própria: o Oracle recusa subquery escalar ao lado de
  -- função de grupo no mesmo SELECT sem GROUP BY.
  SELECT COUNT(*) AS SETUPS,
         SUM(CASE WHEN MINUTOS > {{SETUP_TETO_MIN}} THEN 1 ELSE 0 END)
           AS APONTAMENTO_SUSPEITO
    FROM PARADA
),
AGG AS (
  SELECT
    COUNT(*)                                                       AS SETUPS_VALIDOS,
    ROUND(MEDIAN(MINUTOS),1)                                       AS MEDIANA_MIN,
    ROUND(AVG(MINUTOS),1)                                          AS MEDIA_MIN,
    {{SETUP_PADRAO_MIN}}                                           AS PADRAO_MIN,
    SUM(CASE WHEN MINUTOS > {{SETUP_PADRAO_MIN}} THEN 1 ELSE 0 END) AS ACIMA_PADRAO,
    ROUND(SUM(CASE WHEN MINUTOS > {{SETUP_PADRAO_MIN}} THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*),0) * 100, 1)                           AS PCT_ACIMA_PADRAO,
    ROUND(SUM(GREATEST(MINUTOS - {{SETUP_PADRAO_MIN}}, 0)) / 60, 1) AS HORAS_PERDIDAS
  FROM VALIDA
),
PIOR AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.MIN_MED DESC) AS LISTA
    FROM (SELECT W.NOME, ROUND(MEDIAN(V.MINUTOS)) AS MIN_MED,
                 W.NOME || ': ' || ROUND(MEDIAN(V.MINUTOS)) || ' min ('
                   || COUNT(*) || ' trocas)' AS TXT
            FROM VALIDA V JOIN TPRWCP W ON W.CODWCP = V.CODWCP
           GROUP BY W.NOME
          HAVING COUNT(*) >= 3
           ORDER BY MEDIAN(V.MINUTOS) DESC FETCH FIRST 8 ROWS ONLY) X
)
SELECT T.SETUPS, A.SETUPS_VALIDOS, T.APONTAMENTO_SUSPEITO, A.MEDIANA_MIN,
       A.MEDIA_MIN, A.PADRAO_MIN, A.ACIMA_PADRAO, A.PCT_ACIMA_PADRAO,
       A.HORAS_PERDIDAS, P.LISTA
  FROM AGG A CROSS JOIN TOTAIS T CROSS JOIN PIOR P
