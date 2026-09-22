-- KPI: faturamento_ritmo
-- Pergunta: no ritmo de hoje, bato a meta do mês?
--
-- A META É DIÁRIA: {{META_DIA}} por dia útil nas empresas {{CODEMP_META}}
-- (1 Matriz, 2 Filial, 4 Mundo UD, 14 Extrema). É o mesmo número que limita
-- a agenda de carga — a fábrica carrega e fatura na mesma capacidade, e
-- tratar meta de venda e capacidade de expedição como coisas diferentes é
-- como a agenda acaba com dia de R$ 1,8 milhão ao lado de dia de R$ 37 mil.
--
-- RECORTE DIFERENTE DO RESTO DA MATRIZ, DE PROPÓSITO: os outros KPIs usam
-- 1,2,3,4,14,17,20 ("o grupo"). A meta operacional é só das quatro que
-- produzem e expedem — 3 é a NTR Log (transporte), 17 é o Hyak Group
-- (serviços administrativos) e 20 é a ACIUD. Se um número daqui não bater
-- com outro KPI, o recorte é a primeira coisa a conferir.
--
-- Metodologia (skill sankhya-especialista §2): âncora ATUALCOM='C' +
-- AD_INSEREDASH='S'. NÃO usar TIPMOV='V' — descarta a TOP 3110, que é
-- faturamento real. Filtro de TOP por subquery em CODTIPOPER, nunca por join
-- na TGFTOP, que é versionada e subconta ~65%.
--
-- APURADO EM 22/09/2026 — os últimos 63 dias úteis nas empresas 1,2,4,14:
--   média R$ 364.278/dia | mediana R$ 329.452 | mínimo R$ 43.918 | máximo R$ 1.295.895
--   apenas 11 dos 63 dias (17,5%) bateram os R$ 500 mil
-- A meta está 37% acima da média realizada. Isso é escolha de gestão, não
-- erro de cálculo — mas o KPI nasce vermelho e vai continuar vermelho até a
-- operação mudar, então é bom que a diretoria saiba disso antes de ativar.
--
-- Params: {{CODEMP_META}}  {{META_DIA}}

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
DIAS AS (
  -- Dias úteis do mês (seg-sex; feriado não tratado).
  SELECT
    SUM(CASE WHEN D <= TRUNC(SYSDATE) AND TO_CHAR(D,'DY','NLS_DATE_LANGUAGE=ENGLISH')
              NOT IN ('SAT','SUN') THEN 1 ELSE 0 END) AS UTEIS_DECORRIDOS,
    SUM(CASE WHEN TO_CHAR(D,'DY','NLS_DATE_LANGUAGE=ENGLISH')
              NOT IN ('SAT','SUN') THEN 1 ELSE 0 END) AS UTEIS_TOTAIS
  FROM (
    SELECT TRUNC(SYSDATE,'MM') + LEVEL - 1 AS D FROM DUAL
    CONNECT BY LEVEL <= TO_NUMBER(TO_CHAR(LAST_DAY(SYSDATE),'DD'))
  )
),
POR_DIA AS (
  SELECT TRUNC(CAB.DTNEG) AS DIA, SUM(CAB.VLRNOTA) AS VLR
    FROM TGFCAB CAB /*CC TGFCAB CC*/
   WHERE CAB.STATUSNOTA = 'L'
     AND CAB.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
     AND CAB.CODEMP IN ({{CODEMP_META}})
     AND CAB.CODPARC NOT IN (SELECT CODPARC FROM TSIEMP WHERE CODPARC IS NOT NULL)
     AND CAB.DTNEG >= TRUNC(SYSDATE,'MM')
     AND CAB.DTNEG <  ADD_MONTHS(TRUNC(SYSDATE,'MM'),1)
     AND TO_CHAR(CAB.DTNEG,'DY','NLS_DATE_LANGUAGE=ENGLISH') NOT IN ('SAT','SUN')
   GROUP BY TRUNC(CAB.DTNEG)
),
MTD AS (
  SELECT NVL(SUM(VLR),0) AS REALIZADO,
         COUNT(*) AS DIAS_COM_FATURAMENTO,
         SUM(CASE WHEN VLR >= {{META_DIA}} THEN 1 ELSE 0 END) AS DIAS_NA_META
    FROM POR_DIA
)
SELECT
  ROUND(M.REALIZADO,2)                                          AS REALIZADO_MTD,
  D.UTEIS_DECORRIDOS,
  D.UTEIS_TOTAIS,
  M.DIAS_NA_META,
  {{META_DIA}}                                                  AS META_DIA,
  ROUND({{META_DIA}} * D.UTEIS_TOTAIS, 2)                       AS META_MES,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1), 2)        AS RITMO_DIA_UTIL,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1)
        * D.UTEIS_TOTAIS, 2)                                    AS PROJECAO_FECHAMENTO,
  ROUND(M.REALIZADO / GREATEST(D.UTEIS_DECORRIDOS,1)
        / {{META_DIA}} * 100, 1)                                AS PCT_PROJECAO_META
FROM MTD M CROSS JOIN DIAS D
