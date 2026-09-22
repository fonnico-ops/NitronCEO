-- KPI: setup_maquinas
-- Pergunta: a troca de molde está dentro dos 40 minutos de padrão?
--
-- LACUNA DE DADO — este KPI nasce em modo sombra, de propósito.
--
-- O PADRÃO existe: TPRWCP.TEMPOSETUP = 40 min nas 45 injetoras.
-- O REALIZADO não é mais gravado: AD_PARADAMAQUINA, que tinha o motivo
-- 'SM' = Setup de Maquina no domínio, parou em 31/10/2024.
--
-- APROXIMAÇÃO USADA AQUI: o setup é inferido pela LACUNA entre o último
-- apontamento de ciclo de uma OP e o primeiro apontamento da OP seguinte na
-- mesma injetora (AD_APONTACICLO.CODWCP + AD_TGPAPO.DHAPONTAMENTO).
-- Isso mede tempo de parede — inclui troca de turno, almoço e espera de
-- cartão RFID, exatamente as distorções que a skill do PCP alerta sobre
-- DHPRODUCAO->DHTERMINOPRODUCAO. Por isso: lacunas acima de
-- {{SETUP_TETO_MIN}} minutos são descartadas como "não é setup".
--
-- RESULTADO DA APROXIMAÇÃO, MEDIDO EM 22/09/2026 (janela 7 dias, teto 240 min):
--   102 lacunas medidas | média 6 min | MEDIANA 2 MIN | 6,9% acima de 40 min
-- Mediana de 2 minutos NÃO é troca de molde. A lacuna entre OPs consecutivas
-- está medindo troca de NUCICLO sem parada real, não setup. Ou seja: a
-- aproximação, como está, NÃO MEDE SETUP. O KPI fica em sombra até existir
-- fonte de verdade.
--
-- ANTES DE ATIVAR: voltar a gravar a parada de setup numa tabela viva (o
-- domínio MOTIVO='SM' de AD_PARADAMAQUINA já existia e funcionava até
-- 31/10/2024), ou marcar a troca de molde no app do PCP.
-- Ver docs/achados-de-dados.md.
--
-- Params: {{JANELA_DIAS}}  {{SETUP_TETO_MIN}}

WITH APONT AS (
  SELECT C.CODWCP, A.NUCICLO, A.DHAPONTAMENTO
    FROM AD_TGPAPO A
    JOIN AD_APONTACICLO C ON C.NUCICLO = A.NUCICLO
   WHERE A.DHAPONTAMENTO >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
),
LIM AS (
  SELECT CODWCP, NUCICLO,
         MIN(DHAPONTAMENTO) AS INICIO, MAX(DHAPONTAMENTO) AS FIM
    FROM APONT GROUP BY CODWCP, NUCICLO
),
LACUNA AS (
  SELECT L.CODWCP, L.NUCICLO,
         ROUND((L.INICIO - LAG(L.FIM) OVER (PARTITION BY L.CODWCP
                                            ORDER BY L.INICIO)) * 24 * 60) AS MIN_LACUNA
    FROM LIM L
),
VALIDA AS (
  SELECT LA.CODWCP, LA.MIN_LACUNA, NVL(W.TEMPOSETUP, 40) AS PADRAO
    FROM LACUNA LA
    JOIN TPRWCP W ON W.CODWCP = LA.CODWCP
   WHERE LA.MIN_LACUNA IS NOT NULL
     AND LA.MIN_LACUNA > 0
     AND LA.MIN_LACUNA <= {{SETUP_TETO_MIN}}
)
SELECT
  COUNT(*)                                                     AS TROCAS_MEDIDAS,
  ROUND(AVG(MIN_LACUNA),1)                                     AS MEDIA_MIN,
  ROUND(MEDIAN(MIN_LACUNA),1)                                  AS MEDIANA_MIN,
  MAX(PADRAO)                                                  AS PADRAO_MIN,
  SUM(CASE WHEN MIN_LACUNA > PADRAO THEN 1 ELSE 0 END)         AS ACIMA_PADRAO,
  ROUND(SUM(CASE WHEN MIN_LACUNA > PADRAO THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*),0) * 100, 1)                         AS PCT_ACIMA_PADRAO
FROM VALIDA
