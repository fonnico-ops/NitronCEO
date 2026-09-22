-- KPI: entrega_sem_canhoto
-- Pergunta: quanto faturamos sem ter prova de que foi entregue?
--
-- Canhoto assinado é a prova de entrega. Sem ele, em disputa de cobrança ou
-- alegação de não-recebimento, a empresa não tem o que apresentar — e o
-- título fica frágil justamente quando precisa ser cobrado.
--
-- FONTE: AD_ARQENTREGA, chaveada por NUNOTA (66.993 arquivos em 65.394
-- notas). Foi descoberta pela definição da view AD_VW_TITREC_NF, que já
-- calculava TEMCANHOTO para a fila de títulos a receber; aqui a mesma regra
-- é aplicada ao FATURAMENTO, não só aos títulos em aberto.
--
-- O ACHADO QUE MUDA A COBRANÇA — cobertura por modal, últimos 5 meses:
--
--   mês      entrega própria / NTR     transportadora terceira
--   abr/26   15,0%  (3.862 notas)      65,8%  (1.421 notas)
--   mai/26    9,0%  (5.012 notas)      65,0%  (1.330 notas)
--   jun/26    8,2%  (5.194 notas)      68,8%  (  828 notas)
--   jul/26   13,1%  (3.651 notas)      62,7%  (  773 notas)
--   ago/26    9,5%  (4.395 notas)      60,6%  (1.059 notas)
--
-- Quando a mercadoria vai por transportadora de terceiro, o canhoto volta em
-- 6 de cada 10 entregas. Quando vai pela frota própria/NTR Log, volta em 1 de
-- cada 10 — e a frota própria é quatro vezes o volume. O problema não é o
-- sistema: é o processo de retorno do canhoto da entrega própria.
--
-- Conecta com emissao_ntrlog: a mesma operação que não emite nota de frete
-- também não devolve o comprovante de entrega.
--
-- CARÊNCIA de {{CANHOTO_CARENCIA_DIAS}} dias: nota faturada ontem ainda não
-- tem canhoto de volta por motivo legítimo. Só entra o que já passou do
-- prazo razoável de retorno.
--
-- Aferido 22/09/2026 (90 dias, empresas 1,2,4,14): 16.106 notas faturadas,
-- 18,7% com canhoto. 9.478 notas com mais de 15 dias e sem canhoto, somando
-- R$ 3.996.797,59.
--
-- Params: {{CODEMP_META}}  {{CANHOTO_CARENCIA_DIAS}}  {{JANELA_CANHOTO_DIAS}}
--         {{CODPARC_NTRLOG}}

WITH TOPFAT AS (
  SELECT CODTIPOPER FROM TGFTOP
   WHERE ATUALCOM = 'C' AND NVL(AD_INSEREDASH,'N') = 'S'
),
NF AS (
  SELECT C.NUNOTA, C.NUMNOTA, C.CODPARC, C.VLRNOTA,
         TRUNC(SYSDATE) - TRUNC(C.DTNEG) AS DIAS,
         CASE WHEN NVL(C.CODPARCTRANSP,0) IN (0, {{CODPARC_NTRLOG}})
              THEN 'propria' ELSE 'transportadora' END AS MODAL
    FROM TGFCAB C /*CC TGFCAB CC*/
   WHERE C.STATUSNOTA = 'L'
     AND C.CODTIPOPER IN (SELECT CODTIPOPER FROM TOPFAT)
     AND C.CODEMP IN ({{CODEMP_META}})
     AND C.DTNEG >= TRUNC(SYSDATE) - {{JANELA_CANHOTO_DIAS}}
),
CANH AS (SELECT DISTINCT NUNOTA FROM AD_ARQENTREGA),
BASE AS (
  SELECT N.*, CASE WHEN A.NUNOTA IS NULL THEN 1 ELSE 0 END AS SEM_CANHOTO
    FROM NF N LEFT JOIN CANH A ON A.NUNOTA = N.NUNOTA
),
AGG AS (
  SELECT
    COUNT(*)                                                       AS NOTAS_JANELA,
    ROUND(SUM(CASE WHEN SEM_CANHOTO = 0 THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*),0) * 100, 1)                           AS PCT_COM_CANHOTO,
    SUM(CASE WHEN SEM_CANHOTO = 1 AND DIAS > {{CANHOTO_CARENCIA_DIAS}}
             THEN 1 ELSE 0 END)                                    AS NOTAS_SEM_CANHOTO,
    ROUND(SUM(CASE WHEN SEM_CANHOTO = 1 AND DIAS > {{CANHOTO_CARENCIA_DIAS}}
                   THEN VLRNOTA ELSE 0 END), 2)                    AS VLR_SEM_CANHOTO,
    ROUND(SUM(CASE WHEN MODAL = 'propria' AND SEM_CANHOTO = 0 THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN MODAL = 'propria' THEN 1 ELSE 0 END),0) * 100, 1)
                                                                   AS PCT_CANHOTO_PROPRIA,
    ROUND(SUM(CASE WHEN MODAL = 'transportadora' AND SEM_CANHOTO = 0 THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN MODAL = 'transportadora' THEN 1 ELSE 0 END),0) * 100, 1)
                                                                   AS PCT_CANHOTO_TRANSP
  FROM BASE
),
TOPO AS (
  SELECT LISTAGG(X.TXT, ' · ') WITHIN GROUP (ORDER BY X.VLR DESC) AS LISTA
    FROM (SELECT SUM(B.VLRNOTA) AS VLR,
                 P.NOMEPARC || ': ' || COUNT(*) || ' notas, R$ '
                   || ROUND(SUM(B.VLRNOTA)) AS TXT
            FROM BASE B JOIN TGFPAR P ON P.CODPARC = B.CODPARC
           WHERE B.SEM_CANHOTO = 1 AND B.DIAS > {{CANHOTO_CARENCIA_DIAS}}
           GROUP BY P.NOMEPARC
           ORDER BY SUM(B.VLRNOTA) DESC FETCH FIRST 10 ROWS ONLY) X
)
SELECT A.NOTAS_JANELA, A.PCT_COM_CANHOTO, A.NOTAS_SEM_CANHOTO, A.VLR_SEM_CANHOTO,
       A.PCT_CANHOTO_PROPRIA, A.PCT_CANHOTO_TRANSP, T.LISTA
  FROM AGG A CROSS JOIN TOPO T
