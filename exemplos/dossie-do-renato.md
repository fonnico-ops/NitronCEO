<!-- Gerado por `nitronceo renato --dossie` sobre os fixtures de 22/09/2026.
     É exatamente o material que o Renato recebe na mensagem do usuário —
     a persona e os achados de dados vão separados, no prefixo em cache. -->

# Dossiê da rodada — 22/09/2026 23:13

## Sinais apurados
- Pedidos esperando aprovação ou recusa [comercial] = 180 -> CRÍTICO, dono Ricardo Miyabara
    PEDIDOS_TRAVADOS=87, VLR_TRAVADO=505694.43, DIAS_MAX=180, DIAS_MEDIO=47.6, PARADOS_MAIS_30D=52
    LISTA: (34 pedidos em PIX aguardando recebimento, o mais antigo há 180d; 42 em Tempo Inativo, o mais antigo há 139d)
- Pedidos travados no crédito [financeiro] = 35 -> CRÍTICO, dono Claudia Ribeiro
    PEDIDOS_TRAVADOS=68, VLR_TRAVADO=754488.66, DIAS_MAX=35, DIAS_MEDIO=10.5, PARADOS_MAIS_7D=24
    LISTA: KALUNGA SA — R$ 34174 (35d, Atraso), MATOS & PRADO LTDA — R$ 2085 (32d, Limite Créd. Mensal), SUP.SHOP.DAUTI.DE SAO JOSE DOS CAMPOS II — R$ 4672 (28d, Atraso)
- Grandes devedores [financeiro] = 7 -> CRÍTICO, dono Claudia Ribeiro
    DEVEDORES_ACIMA_PISO=14, VLR_CONCENTRADO=1804739.47, PIOR_ATRASO=342, AINDA_COMPRANDO=7, VLR_FATURADO_A_DEVEDOR=1511887.35
    LISTA: 001 - INTERLAGOS - SP — R$ 418413 (286d, AINDA COMPRANDO R$ 563204) · TUBARAO 65 — R$ 284404 (120d) · KALUNGA SA — R$ 253176 (30d, AINDA COMPRANDO R$ 366993)
- Despesa fora de Compras acima do padrão [financeiro] = R$ 3.279.138,75 -> CRÍTICO, dono Claudia Ribeiro
    NATUREZAS_ESTOURADAS=5, EXCESSO_TOTAL=3279138.75, MAIOR_ESTOURO_PCT=265.3
    LISTA: Emprestimos e Financiamentos: R$ 4678714 vs média R$ 1763563 (265%) · Lucros e Dividendos: R$ 796227 vs média R$ 583610 (136%) · Devoluções de vendas: R$ 350774 vs média R$ 267292 (131%)
- Emissão da NTR Log contra o frete pago [logistica] = 2.6% -> CRÍTICO, dono Expedição e Forla Silva
    FRETE_PAGO_MES=842709.4, TITULOS_FRETE=636, TITULOS_SEM_NOTA=636, EMITIDO_NTRLOG=21567.12, NOTAS_EMITIDAS=626, GAP_EMISSAO=821142.28, PCT_COBERTURA=2.6
- Agenda de carga contra a capacidade [logistica] = R$ 1.715.609,62 -> CRÍTICO, dono Expedição e Forla Silva
    DIAS_AGENDADOS=11, DIAS_ESTOURADOS=2, DIAS_OCIOSOS=9, VLR_A_REMANEJAR=1715609.62, VLR_OCIOSO=3512518.91, VLR_AGENDADO_TOTAL=3703090.71, ORDENS_ABANDONADAS=58
    LISTA: 22/09: R$ 840451 (1,7x a capacidade, 19 ordens abertas) · 29/09: R$ 37728 (dia ocioso) · 01/10: R$ 0 (dia ocioso) · 02/10: R$ 1875158 (3,8x a capacidade, 28 ordens abertas)
- Faturamento sem canhoto de entrega [logistica] = R$ 3.996.797,59 -> CRÍTICO, dono Expedição e Forla Silva
    NOTAS_JANELA=16106, PCT_COM_CANHOTO=18.7, NOTAS_SEM_CANHOTO=9478, VLR_SEM_CANHOTO=3996797.59, PCT_CANHOTO_PROPRIA=10.3, PCT_CANHOTO_TRANSP=54.5
    LISTA: NATURA FILIAL CABREUVA: 6 notas, R$ 1136353 · HYAK: 7 notas, R$ 567074 · CASA E VIDEO: 1 notas, R$ 244284 · MUNDO 5,99: 2 notas, R$ 109274
- Paradas sem motivo apontado [producao] = 58.4% -> CRÍTICO, dono Alex Souza e Charles Silva
    PARADAS=3066, SEM_MOTIVO=1791, PCT_SEM_MOTIVO=58.4, HORAS_SEM_MOTIVO=6440.2, HORAS_PARADAS_TOTAL=15668.4
- Ordens de serviço abertas [producao] = 483 -> CRÍTICO, dono Alex Souza e Charles Silva
    ABERTAS=503, ABERTAS_VELHAS=483, ABERTAS_ACIMA_180D=162, COM_EQPTO_PARADO=330, IDADE_MEDIANA=138, IDADE_MAX=602, PREVENTIVAS=50, FECHADAS_365D=1804, MEDIANA_FECHAMENTO=0.8, FECHADAS_ACIMA_30D=140
    LISTA: INDUSTRIAL: 222 abertas, mediana 133d, 184 com equipamento parado · PREDIAL: 168 abertas, mediana 171d, 108 com equipamento parado · MOLDES: 108 abertas, mediana 93d, 34 com equipamento parado · GEN: 5 abertas, mediana 22d, 4 com equipamento parado
- Preventiva contra corretiva [producao] = 7.0% -> CRÍTICO, dono Alex Souza e Charles Silva
    OS_JANELA=1022, PREVENTIVAS=72, CORRETIVAS=950, PCT_PREVENTIVA=7.0
    LISTA: MOLDES: 8% preventiva em 630 OS · INDUSTRIAL: 5% preventiva em 235 OS · PREDIAL: 9% preventiva em 137 OS · GEN: 0% preventiva em 20 OS
- Performance por representante [comercial] = 26 -> VERMELHO, dono Ricardo Miyabara (SOMBRA — não notifica ninguém)
    REPRESENTANTES=53, QTD_ABAIXO_META=26, QTD_ZERADOS=7
    LISTA: ANNA CAROLINA (0%), ARY CARVALHO (0%), FABIOLA (0%), FRANCIEL (0%)
- Performance por canal [comercial] = 61.4% -> VERMELHO, dono Ricardo Miyabara (SOMBRA — não notifica ninguém)
    PCT_PIOR_CANAL_VS_MEDIA=61.4, ROTULO=Outside, VLR_SEM_CANAL=1716600.96, PCT_SEM_CANAL=27.4
- Produtos que pararam de vender [comercial] = R$ 3.921.906,88 -> VERMELHO, dono Ricardo Miyabara
    PRODUTOS_EM_QUEDA=129, VLR_PERDIDO=3921906.88, PARARAM_DE_VENDER=7, QUEDA_ACIMA_50PCT=70
    LISTA: LIXEIRA RATTAN COM PEDAL - BRANCA 6L (052/B): R$ 285623 -> R$ 135219 (47%) · GAVETEIRO COM 4 GAVETAS - PRETA (004/4P): R$ 218368 -> R$ 94631 (43%) · ESCORREDOR DE PRATOS - PRETO (059/P): R$ 136950 -> R$ 47446 (35%)
- Estoque de produto inativo [comercial] = R$ 607.635,72 -> VERMELHO, dono Ricardo Miyabara
    PRODUTOS=57, QTD_TOTAL=304723, VLR_CUSTO=607635.72, VLR_LIQUIDAVEL=67678.51, VLR_SEM_MERCADO=539957.21, COM_VENDA_180D=14, SEM_CUSTO_CADASTRADO=8
    LISTA: CESTO ORG. VERSATIL LAVANDERIA-FSC1396372: 253036 un, R$ 502074 (sem venda em 180d) · CARRETILHA LISA CORTADORA - BRANCA: 4247 un, R$ 17973 (ainda vende) · CACAROLA MICRO-ONDAS - ROSA 1,5L (014): 5721 un, R$ 14075 (ainda vende)
- Gastos de compra fora do padrão [compras] = R$ 531.800,46 -> VERMELHO, dono Cristiane Alves
    NATUREZAS_ESTOURADAS=3, EXCESSO_TOTAL=531800.46, MAIOR_ESTOURO_PCT=186.8
    LISTA: Injeção Tercerizada: R$ 578941 vs média R$ 309947 (187%) · Adiantamento a Fornecedores: R$ 485055 vs média R$ 347260 (140%) · Embalagens: R$ 274954 vs média R$ 149942 (183%)
- Despesa sobre faturamento [compras] = 120.9% -> VERMELHO, dono Cristiane Alves (SOMBRA — não notifica ninguém)
    DESPESA_MES=14384301.62, FATURAMENTO_MES=7468338.1, PCT_MES=192.6, PCT_MEDIA_12M=159.3, PCT_VS_PADRAO=120.9
- Mix do catálogo no e-commerce [ecommerce] = 120 -> VERMELHO, dono Ana Julia
    SKUS_VENDIDOS=382, VLR_TOTAL=309402.02, SKUS_ATE_80PCT=90, SKUS_CAUDA=120, VLR_CAUDA=5700.38, SKUS_ATE_2_UNID=83, LISTA_CAUDA=SABONETEIRA COM TELA FLAT - PRETO: R$ 7,5 · PORTA LEITE DE CAIXINHA - BRANCO: R$ 11,99 · COPO BABY COM TAMPA - PANDA 250 ML: R$ 12,9
    LISTA: POTE ALTO RETANGULAR - TRANSPARENTE 4,6L (025/7): R$ 13789 (41 un) · FRASQUEIRA MEDICAMENTOS - BRANCA 6,2L (142): R$ 11264 (258 un) · GAVETEIRO COM 4 GAVETAS - PRETA (004/4P): R$ 10834 (238 un)
- Recebíveis vencidos [financeiro] = R$ 9.728.499,68 -> VERMELHO, dono Claudia Ribeiro
    TITULOS=3352, VLR_VENCIDO=9728499.68, VLR_ATE_30D=1120000.0, VLR_ACIMA_90D=6400000.0
    LISTA: (top 10 devedores)
- Ritmo de faturamento [logistica] = 76.9% -> VERMELHO, dono Expedição e Forla Silva
    REALIZADO_MTD=6149212.43, UTEIS_DECORRIDOS=16, UTEIS_TOTAIS=22, DIAS_NA_META=5, META_DIA=500000, META_MES=11000000, RITMO_DIA_UTIL=384325.78, PROJECAO_FECHAMENTO=8455167.09, PCT_PROJECAO_META=76.9
- Entregas reagendadas [logistica] = 16.9% -> VERMELHO, dono Expedição e Forla Silva (SOMBRA — não notifica ninguém)
    AGENDAMENTOS=555, REAGENDADOS=94, RECUSAS=0, NAO_ATENDE=0, PCT_REAGENDADO=16.9
- Suspensos que continuam vendendo [pcp] = R$ 1.581.142,14 -> VERMELHO, dono Anderson Lourenço
    SUSPENSOS_TOTAL=652, COM_VENDA_180D=421, COM_PEDIDO_ABERTO=165, VLR_VENDIDO_180D=1581142.14, VLR_NA_CARTEIRA=27646.9, CANDIDATOS_RELEVANTES=87
    LISTA: (15 produtos suspensos com maior venda nos últimos 180 dias)
- Tempo de setup das injetoras [producao] = 74.2% -> VERMELHO, dono Alex Souza e Charles Silva
    SETUPS=217, SETUPS_VALIDOS=209, APONTAMENTO_SUSPEITO=8, MEDIANA_MIN=115.8, MEDIA_MIN=238.7, PADRAO_MIN=40, ACIMA_PADRAO=155, PCT_ACIMA_PADRAO=74.2, HORAS_PERDIDAS=711.8
    LISTA: INJETORA 3: 547 min (3 trocas) · INJETORA 19: 496 min (15 trocas) · INJETORA 24: 409 min (3 trocas)
- Ciclo de injeção acima do padrão [producao] = 128.5% -> VERMELHO, dono Alex Souza e Charles Silva
    APONTAMENTOS=276713, PCT_MEDIANO=128.5, ACIMA_25PCT=146881, ACIMA_50PCT=63020, MAQUINAS=45, MAQUINAS_ACIMA_140=10
    LISTA: INJETORA 7: 18s -> 32,4s (178%) · INJETORA 22: 18,8s -> 30,6s (162%) · INJETORA 2: 19s -> 34,3s (160%) · INJETORA 44: 20s -> 25,7s (155%) · INJETORA 9: 16,8s -> 27,8s (154%)
- Injetora parada por molde [projetos] = 773 -> VERMELHO, dono Projetos
    PARADAS=69, ABERTAS_AGORA=1, HORAS_PARADAS=773.4, MEDIA_MIN=672.5, MAQUINAS_AFETADAS=30
    LISTA: INJETORA 31: 110,3h em 3 paradas · INJETORA 25: 95,7h em 4 paradas · INJETORA 28: 61,2h em 8 paradas
- Injeção fora da Nitron [projetos] = R$ 1.652.190,00 -> VERMELHO, dono Projetos
    VLR_TRIMESTRE=1652190.0, VLR_12M=4400167.95, VLR_TRIM_ANO_PASSADO=876215.34, FORNECEDORES=8
    LISTA: TANAMU: R$ 3195053 em 12m · MAGIC TOYS DO BRASIL: R$ 465390 em 12m · L PLAST FERRAMENTARIA: R$ 253404 em 12m · J KOVACS: R$ 237291 em 12m
- Ritmo de entrada de pedidos [comercial] = 91.8% -> amarelo, dono Ricardo Miyabara
    VLR_MTD=4331656.45, QTD_MTD=4350, VLR_DIA_ATUAL=196893.47, VLR_DIA_MEDIA_90D=214500.0, PCT_VS_MEDIA_90D=91.8
- Fluxo de caixa dos próximos 7 dias [financeiro] = R$ -142.357,40 -> amarelo, dono Claudia Ribeiro
    RECEBER_D0_D7=1675470.84, PAGAR_D0_D7=1817828.24, SALDO_D0_D7=-142357.4, RECEBER_D8_D30=5676974.53, PAGAR_D8_D30=13426196.66, SALDO_D8_D30=-7749222.13, SALDO_D0_D30=-7891579.53
- Notas com reentrada / refaturamento [logistica] = 41 -> amarelo, dono Expedição e Forla Silva
    QTD_REFATURADAS=17, VLR_REFATURADO=186222.34, QTD_COM_DEVOLUCAO_VINCULADA=58, QTD_EM_ABERTO=41
- Produtos sem estoque com pedido na carteira [pcp] = R$ 282.133,90 -> amarelo, dono Anderson Lourenço
    ITENS_CARTEIRA=605, ITENS_SEM_SALDO=28, ITENS_SALDO_PARCIAL=12, VLR_EM_RISCO=282133.9, ENDERECOS_NEGATIVOS=3980
    LISTA: (top 10 itens ativos sem saldo)
- O que o PCP precisa programar [pcp] = R$ 386.621,05 -> amarelo, dono Anderson Lourenço
    ITENS_PARA_PROGRAMAR=15, VLR_MES_EXPOSTO=386621.05, ITENS_SEM_SALDO=9
    LISTA: KIT NITRONBOX C/ 3PCS TRAVAS PRETAS — R$ 189707/mês, SEM SALDO · KIT MANTIMENTOS COM 5 PECAS - PRETO (152) — R$ 30983/mês, 12,4d de cobertura
- Injetoras paradas agora [producao] = 3 -> amarelo, dono Alex Souza e Charles Silva
    MONITORADAS=45, PARADAS_ABERTAS=13, NAO_PROGRAMADAS=4, PARADAS_60MIN=3, SEM_MOTIVO=2, REFEICAO_LONGA=7
    LISTA: INJETORA 15: MANUTENÇÃO DE MOLDE há 143 min · INJETORA 35: (SEM MOTIVO) há 85 min · INJETORA 29: (SEM MOTIVO) há 64 min · INJETORA 38: SETUP há 36 min
- Carteira disponível para faturar [comercial] = 4 -> verde, dono Ricardo Miyabara
    PEDIDOS_CARTEIRA=727, VLR_CARTEIRA=2229298.53, VLR_COM_ESTOQUE=2011711.42, VLR_SEM_ESTOQUE=217587.11, DIAS_DE_META=4.0
- Emissão da Teak Brazil [compras] = 0 -> verde, dono Cristiane Alves
    DIAS_SEM_EMITIR=0, NOTAS_JANELA=15, VLR_JANELA=247774.92, MEDIA_MES_6M=240510.69
    LISTA: TEAK BRAZIL: 60 notas em 6 meses | TEAK BRAZIL (RONDÔNIA): 0 notas em 6 meses
- Ritmo de vendas do e-commerce [ecommerce] = 154.7% -> verde, dono Ana Julia
    VLR_MTD=84901.23, PEDIDOS_MTD=3257, TICKET_MTD=26.07, TICKET_MEDIO_HIST=28.34, VLR_DIA_ATUAL=3859.15, VLR_DIA_HIST=2495.04, PCT_VS_MEDIA=154.7
    LISTA: SHOPEE / Shopee - MUNDO UD: 1089 pedidos, R$ 19774 · SHOPEE / Shopee - NITRON: 559 pedidos, R$ 9070 · MERCADO_LIVRE / MUNDO UD: 172 pedidos, R$ 7643 · MERCADO_LIVRE / NITRON VIDA CASA: 23 pedidos, R$ 1049
- Ordens de carga montadas por dia [logistica] = 54 -> verde, dono Expedição e Forla Silva
    ORDENS_ONTEM=54, FECHADAS_ONTEM=20, MEDIA_7D=27.6, ABERTAS_ATRASADAS=572
- Notas devolvidas [logistica] = 0.5% -> verde, dono Expedição e Forla Silva
    NOTAS_DEVOLVIDAS=16, VLR_DEVOLVIDO=48586.67, VLR_FATURADO=9107452.19, PCT_SOBRE_FATURAMENTO=0.53
- Produtos com estoque curto [pcp] = 68 -> verde, dono Anderson Lourenço
    PRODUTOS_COM_GIRO=573, COB_MENOR_7D=62, COB_ABAIXO_ALERTA=68, SALDO_NAO_POSITIVO=59, VLR_MES_EM_RISCO=434280.76
    LISTA: KIT NITRONBOX C/ 3PCS TRAVAS PRETAS (sem saldo), KIT MANTIMENTOS COM 5 PECAS - PRETO (152) (12,4d), ORGANIZA TUDO MEDIO-138 (6,7d)

## Cobranças em aberto
- [f914b5] Pedido parado há 35 dias esperando crédito — Claudia Ribeiro, 2h, 0 escalonamento(s)
- [a841c8] R$ 1.715.609,62 agendados acima da capacidade de carga — Expedição e Forla Silva, 2h, 0 escalonamento(s)
- [e354ac] Ritmo de faturamento em 76.9% da meta diária — Expedição e Forla Silva, 4h, 0 escalonamento(s)
- [7f13d6] Pedido parado há 180 dias sem aprovação nem recusa — Ricardo Miyabara, 4h, 0 escalonamento(s)
- [ab2231] 74.2% das trocas de molde estouraram os 40 minutos — Alex Souza e Charles Silva, 8h, 0 escalonamento(s)
- [3207fe] Ciclo mediano em 128.5% do padrão de cadastro — Alex Souza e Charles Silva, 8h, 0 escalonamento(s)
- [ca6f82] 7 grandes devedores continuam comprando — Claudia Ribeiro, 12h, 0 escalonamento(s)
- [dbb037] NTR Log emitiu apenas 2.6% do frete que a Nitron pagou — Expedição e Forla Silva, 12h, 0 escalonamento(s)
- [b8f7e4] R$ 9.728.499,68 vencidos a receber — Claudia Ribeiro, 24h, 0 escalonamento(s)
- [f75d69] R$ 3.279.138,75 de despesa acima do padrão fora de Compras — Claudia Ribeiro, 24h, 0 escalonamento(s)
- [23f0dc] R$ 3.921.906,88 a menos nos produtos que já tinham performance — Ricardo Miyabara, 24h, 0 escalonamento(s)
- [0414f8] 773 horas de injetora paradas por molde em 30 dias — Projetos, 24h, 0 escalonamento(s)
- [94c25c] 58.4% das paradas sem motivo apontado — Alex Souza e Charles Silva, 24h, 0 escalonamento(s)
- [cce471] 483 ordens de serviço abertas há mais de 30 dias — Alex Souza e Charles Silva, 24h, 0 escalonamento(s)
- [b354d6] Só 7.0% das ordens de serviço são preventivas — Alex Souza e Charles Silva, 24h, 0 escalonamento(s)
- [f9bbcc] R$ 3.996.797,59 faturados há mais de 15 dias sem canhoto — Expedição e Forla Silva, 24h, 0 escalonamento(s)
- [1a96e3] R$ 531.800,46 de gasto de compra acima do padrão — Cristiane Alves, 48h, 0 escalonamento(s)
- [61558c] R$ 1.581.142,14 vendidos em 180 dias de produtos que estão suspensos — Anderson Lourenço, 48h, 0 escalonamento(s)
- [8a54eb] R$ 1.652.190,00 de injeção terceirizada no trimestre — Projetos, 48h, 0 escalonamento(s)
- [7914b5] R$ 607.635,72 parados em produto inativo — Ricardo Miyabara, 48h, 0 escalonamento(s)
- [e12fbf] 120 SKUs venderam menos de R$ 100 em 90 dias — Ana Julia, 48h, 0 escalonamento(s)
