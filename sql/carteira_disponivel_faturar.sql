-- KPI: carteira_disponivel_faturar
-- Pergunta: tem pedido com estoque suficiente para sustentar a meta do dia?
--
-- Não adianta cobrar {{META_DIA}} por dia sem saber se existe o que faturar.
-- Este KPI responde a pergunta que vem antes da meta: quantos dias de meta a
-- carteira atendível sustenta hoje.
--
-- A carteira é a roteirizável (skill de roteirização): TIPMOV='P',
-- STATUSNOTA='L', PENDENTE='S', sem ordem de carga, com corte temporal.
-- O saldo exclui CODLOCAL {{LOCAL_TRANSFERENCIA}} (conta de contrapartida) e
-- a CODEMP 1 (dado corrompido) — ver ruptura_estoque.sql.
--
-- SIMPLIFICAÇÃO DECLARADA: a disponibilidade é avaliada item a item contra o
-- saldo, SEM alocação sequencial. Dois pedidos do mesmo SKU podem ambos
-- aparecer como atendíveis quando o saldo só cobre um. Isso infla um pouco o
-- número. A alocação sequencial correta é trabalho da skill de roteirização,
-- que roda no momento de montar a carga; aqui o que importa é a ordem de
-- grandeza — "tenho 4 dias de meta na mão" ou "tenho meio dia".
--
-- APURADO EM 22/09/2026 (empresas 1,2,4,14, carteira de 45 dias):
--   727 pedidos, R$ 2.229.298,53 na carteira
--   R$ 2.011.711,42 COM estoque  = 4,0 dias de meta
--   R$   217.587,11 SEM estoque  -> esses são do PCP, não do comercial
--
-- A leitura que importa: a carteira atendível NÃO é o gargalo hoje. Se o dia
-- não bate R$ 500 mil com 4 dias de meta disponíveis, o gargalo está na
-- expedição ou na agenda de carga, não na falta de pedido.
--
-- Params: {{CODEMP_META}}  {{CODEMP_SALDO}}  {{LOCAL_TRANSFERENCIA}}
--         {{CARTEIRA_DIAS}}  {{META_DIA}}

WITH CART AS (
  SELECT C.NUNOTA, I.CODPROD, I.QTDNEG,
         I.VLRTOT - NVL(I.VLRDESC,0) AS VLR
    FROM TGFCAB C /*CC TGFCAB CC*/
    JOIN TGFITE I ON I.NUNOTA = C.NUNOTA
   WHERE C.TIPMOV = 'P'
     AND C.STATUSNOTA = 'L'
     AND NVL(C.PENDENTE,'N') = 'S'
     AND NVL(C.ORDEMCARGA,0) = 0
     AND C.CODEMP IN ({{CODEMP_META}})
     AND C.DTNEG >= TRUNC(SYSDATE) - {{CARTEIRA_DIAS}}
),
SALDO AS (
  SELECT CODPROD, SUM(NVL(ESTOQUE,0)) AS FISICO
    FROM TGFEST
   WHERE CODEMP IN ({{CODEMP_SALDO}})
     AND CODLOCAL <> {{LOCAL_TRANSFERENCIA}}
     AND NVL(ATIVO,'S') = 'S'
   GROUP BY CODPROD
)
SELECT
  COUNT(DISTINCT C.NUNOTA)                                        AS PEDIDOS_CARTEIRA,
  ROUND(SUM(C.VLR),2)                                             AS VLR_CARTEIRA,
  ROUND(SUM(CASE WHEN NVL(S.FISICO,0) >= C.QTDNEG
                 THEN C.VLR ELSE 0 END),2)                        AS VLR_COM_ESTOQUE,
  ROUND(SUM(CASE WHEN NVL(S.FISICO,0) < C.QTDNEG
                 THEN C.VLR ELSE 0 END),2)                        AS VLR_SEM_ESTOQUE,
  ROUND(SUM(CASE WHEN NVL(S.FISICO,0) >= C.QTDNEG
                 THEN C.VLR ELSE 0 END) / {{META_DIA}}, 1)        AS DIAS_DE_META
FROM CART C LEFT JOIN SALDO S ON S.CODPROD = C.CODPROD
