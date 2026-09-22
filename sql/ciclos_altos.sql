-- KPI: ciclos_altos
-- Pergunta: quanto a injeção está rodando mais devagar que o padrão?
--
-- AD_TGPAPO.CICLOREAL é o tempo real por tiro, em segundos, e CICLOBASE é o
-- padrão do par produto × injetora. A skill do PCP é explícita: CICLOREAL é
-- a régua confiável de ritmo, e NÃO se deve usar o tempo de parede de
-- AD_APONTACICLO (DHPRODUCAO -> DHTERMINOPRODUCAO), que varia 12x para o
-- mesmo par porque inclui parada, fim de turno e domingo.
--
-- Ciclo alto é perda de capacidade direta e silenciosa: a máquina está
-- ligada, o apontamento acontece, ninguém reclama — e a fábrica entrega
-- menos peça por hora do que o plano assumiu. Diferente da parada, que salta
-- aos olhos.
--
-- APURADO EM 22/09/2026 (30 dias, 291.427 apontamentos):
--   MEDIANA em 128,5% do ciclo base — metade da produção roda 28% mais lenta
--   201.734 apontamentos acima de +10% | 146.857 acima de +25% | 63.007 acima de +50%
--   14.756 apontamentos sem CICLOBASE cadastrado ficam fora do cálculo
--
--   Piores injetoras por mediana (base -> real):
--     INJETORA 7    18,0s -> 32,4s   178%
--     INJETORA 22   18,8s -> 30,6s   162%
--     INJETORA 2    19,0s -> 34,3s   160%
--     INJETORA 44   20,0s -> 25,7s   155%
--     INJETORA 9    16,8s -> 27,8s   154%
--
--   Cruzamento que vale a conversa: a INJETORA 19 aparece aqui a 140% E é a
--   pior em tempo de setup (mediana de 496 min). Mesma máquina, dois
--   problemas — ou é a máquina, ou é quem opera.
--
-- MEDIANA por máquina, com piso de {{CICLO_MIN_APONTAMENTOS}} apontamentos:
-- média se move com um tiro anômalo, e máquina com 20 apontamentos no mês
-- não sustenta conclusão.
--
-- CUIDADO AO LER: ciclo base alto demais no cadastro esconde o problema, e
-- base baixa demais inventa um. Quando uma máquina aparecer muito fora,
-- conferir o cadastro do par produto × injetora antes de cobrar o turno.
--
-- Params: {{JANELA_DIAS}}  {{CICLO_MIN_APONTAMENTOS}}

WITH APONT AS (
  SELECT C.CODWCP, A.CICLOREAL, A.CICLOBASE,
         A.CICLOREAL / A.CICLOBASE * 100 AS PCT
    FROM AD_TGPAPO A
    JOIN AD_APONTACICLO C ON C.NUCICLO = A.NUCICLO
   WHERE A.DHAPONTAMENTO >= TRUNC(SYSDATE) - {{JANELA_DIAS}}
     AND A.CICLOBASE > 0
     AND A.CICLOREAL > 0
),
AGG AS (
  SELECT COUNT(*) AS APONTAMENTOS,
         ROUND(MEDIAN(PCT),1) AS PCT_MEDIANO,
         SUM(CASE WHEN PCT > 125 THEN 1 ELSE 0 END) AS ACIMA_25PCT,
         SUM(CASE WHEN PCT > 150 THEN 1 ELSE 0 END) AS ACIMA_50PCT,
         COUNT(DISTINCT CODWCP) AS MAQUINAS
    FROM APONT
),
POR_MAQ AS (
  SELECT CODWCP, COUNT(*) AS N, MEDIAN(PCT) AS PCT_MED,
         MEDIAN(CICLOBASE) AS BASE, MEDIAN(CICLOREAL) AS REAL_
    FROM APONT GROUP BY CODWCP
  HAVING COUNT(*) >= {{CICLO_MIN_APONTAMENTOS}}
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.PCT_MED DESC) AS LISTA
    FROM (SELECT M.PCT_MED,
                 W.NOME || ': ' || ROUND(M.BASE,1) || 's -> ' || ROUND(M.REAL_,1)
                   || 's (' || ROUND(M.PCT_MED) || '%)' AS TXT
            FROM POR_MAQ M JOIN TPRWCP W ON W.CODWCP = M.CODWCP
           ORDER BY M.PCT_MED DESC FETCH FIRST 10 ROWS ONLY) X
),
FORA AS (
  SELECT COUNT(*) AS MAQUINAS_ACIMA_140
    FROM POR_MAQ WHERE PCT_MED > 140
)
SELECT A.APONTAMENTOS, A.PCT_MEDIANO, A.ACIMA_25PCT, A.ACIMA_50PCT,
       A.MAQUINAS, F.MAQUINAS_ACIMA_140, T.LISTA
  FROM AGG A CROSS JOIN FORA F CROSS JOIN TOPO T
