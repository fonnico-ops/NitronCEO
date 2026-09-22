-- KPI: paradas_sem_motivo
-- Pergunta: a fábrica sabe por que parou?
--
-- 1.791 das 3.066 paradas dos últimos 30 dias — 58% — estão SEM MOTIVO
-- apontado, somando 386.411 minutos (6.440 horas). É a maior linha da
-- tabela de paradas, maior que setup e manutenção juntos.
--
-- Isso não é um indicador de produção: é um indicador sobre o INDICADOR.
-- Enquanto 58% do tempo parado não tem causa, nenhum plano de redução de
-- parada pode ser feito, e os KPIs de setup e de molde estão medindo só a
-- parte que alguém se deu ao trabalho de classificar.
--
-- O motivo {{MOTIVO_LIBERADO}} ("LIBERADO", 757 paradas / 323.064 min) fica
-- de fora do numerador: tem código, então foi apontado. Se na prática for
-- usado como "não sei", vale rever — mas isso é decisão da produção, não
-- suposição desta query.
--
-- Params: {{JANELA_DIAS}}

WITH PARADA AS (
  SELECT I.AD_CODMTP,
         (NVL(I.DHFINAL, SYSDATE) - I.DHINCIAL) * 1440 AS MINUTOS
    FROM TPRIWC I /*CC TPRIWC CC*/
   WHERE I.DHINCIAL >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
)
SELECT
  COUNT(*)                                                      AS PARADAS,
  SUM(CASE WHEN AD_CODMTP IS NULL THEN 1 ELSE 0 END)            AS SEM_MOTIVO,
  ROUND(SUM(CASE WHEN AD_CODMTP IS NULL THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*),0) * 100, 1)                          AS PCT_SEM_MOTIVO,
  ROUND(NVL(SUM(CASE WHEN AD_CODMTP IS NULL THEN MINUTOS END),0)/60, 1)
                                                                AS HORAS_SEM_MOTIVO,
  ROUND(NVL(SUM(MINUTOS),0)/60, 1)                              AS HORAS_PARADAS_TOTAL
FROM PARADA
