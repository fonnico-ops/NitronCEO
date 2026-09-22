# Achados de dados — apuração de 22/09/2026

Tudo aqui foi verificado contra a produção, não deduzido. É a parte mais útil
deste repositório: define **o que dá para cobrar hoje** e **o que precisa ser
instrumentado antes**.

---

## 1. Tabelas mortas que parecem vivas

Três tabelas ainda existem, têm volume e enganam quem escreve SQL por nome:

| Tabela | Última gravação | O que usar no lugar |
|---|---|---|
| `AD_PARADAMAQUINA` | **31/10/2024** | `TPRWCP.AD_DHCICLO` (batimento IoT) |
| `AD_CARGADIARIA` | **20/05/2026** | `TGFORD` (nativa, viva) |
| `AD_ORDENSCARGA` / `AD_PEDIDOSCARGA` | idem | `TGFORD` |

`AD_PARADAMAQUINA` é a mais cara das três: ela tinha o domínio de motivo já
pronto (`SM` = Setup de Máquina, `FM` = Falta de Matéria Prima, `MM` =
Manutenção de Molde, e mais 12). Enquanto ela viveu, a fábrica sabia **por que**
parava. Hoje só sabe **que** parou.

---

## 2. Máquinas paradas — dá para cobrar hoje

`TPRWCP` tem 45 injetoras com `AD_MONITORADO='S'` e sinal vivo: em 22/09/2026
16:45 o último ciclo da maioria tinha menos de um minuto.

O sinal confiável é **tempo desde `AD_DHCICLO`**, não o estado declarado:
`AD_ESTADOATUAL` está **100% nulo** em todas as 45.

Aferição do momento: 45 monitoradas, 1 parada há mais de 60 minutos
(INJETORA 41, último ciclo às 10:49).

**Limite do KPI:** ele diz *que* parou e *há quanto tempo*. Não diz *por quê* —
e é exatamente isso que a cobrança pede ao gerente de produção. Se a Nitron
voltar a gravar o motivo, o KPI passa a cobrar a causa em vez do sintoma.

---

## 3. Setup de máquina — não é mensurável hoje

O padrão existe: `TPRWCP.TEMPOSETUP` = 40 min nas 45 injetoras.
O realizado não é gravado desde 31/10/2024.

Tentamos inferir o setup pela lacuna entre o último apontamento de ciclo de uma
OP e o primeiro da OP seguinte na mesma injetora. Resultado medido (7 dias):

```
102 lacunas | média 6 min | MEDIANA 2 MIN | 6,9% acima de 40 min
```

**Mediana de 2 minutos não é troca de molde.** A lacuna está medindo troca de
`NUCICLO` sem parada física. A aproximação não serve.

**Para destravar,** uma das duas:
- voltar a gravar a parada de setup numa tabela viva (o domínio `MOTIVO='SM'`
  já existia e funcionava); ou
- marcar início/fim de troca de molde no app do PCP, que já escreve em
  `AD_APONTACICLO` a cada ~120 s.

Até lá o KPI fica em sombra. É melhor do que publicar 6,9% e deixar a produção
ser cobrada por um número que não mede o que diz medir.

---

## 4. Devoluções — a armadilha da TOP 2203

`TIPMOV='D'` cru **infla a devolução em cerca de 3×**. Composição do 3º tri/26:

| TOP | Descrição | Valor | É devolução de cliente? |
|---|---|---|---|
| 2203 | Devolução Simbólica Consignado | R$ 1.426.216,82 | **não** — acerto de consignação |
| 5205 | Devolução de Venda NF Própria | R$ 535.691,37 | sim |
| 2201 | Devolução de Venda NF Própria | R$ 260.837,66 | sim |
| 2206 | Devolução de Venda s/ Estoque | R$ 61.475,01 | sim |
| 2215 | devolução site | R$ 21.722,54 | sim |

Com a 2203 dentro, a devolução dos últimos 30 dias apareceria perto de 11% do
faturamento. Excluindo-a: **0,53%** (16 notas, R$ 48.586,67 sobre
R$ 9.107.452,19). A diferença entre "crise de qualidade" e "operação saudável"
era uma TOP.

---

## 5. Canal de venda — 27% do faturamento sem classificação

`TGFCAB.AD_ORIGEM` é o campo de canal. Em set/26:

| Canal | Notas | Valor |
|---|---|---|
| Representante | 332 | R$ 2.642.228,33 |
| **(nulo)** | **4.079** | **R$ 1.716.600,96** |
| FORÇA DE VENDAS | 74 | R$ 867.678,02 |
| Farmer | 172 | R$ 670.780,40 |
| Gestor | 209 | R$ 347.882,29 |
| Outside | 3 | R$ 21.516,56 |

27% do valor não tem canal. Qualquer ranking de canal hoje é enviesado, e
cobrar o time comercial com ele é cobrar com número errado. **É correção de
cadastro, não de SQL** — e é barata.

---

## 6. Estoque — a conta de transferência destruía o saldo

**Este é o achado mais caro da apuração, e invalidava um KPI já entregue.**

`CODLOCAL = 1080000` ("Estoque para Transferência") é conta de
**contrapartida**: fica negativa por construção. Somar todos os `CODLOCAL`
inverte o sinal do saldo dos itens de maior giro.

`PA DE LIXO COM CABO (268)`, campeão de venda, na empresa 2:

| CODLOCAL | Local | Estoque |
|---|---|---|
| 1080000 | Estoque para Transferência | **−158.364** ← contrapartida |
| 2990314 | Preparação 14 | +21.444 |
| 2990301 | Preparação 1 | +7.584 |
| 2071101 | G1101 | +3.696 |
| … | demais endereços | … |

Somando tudo: **−123.641 unidades**. Excluindo a 1080000: **+28.241**.

Efeito nos KPIs, depois da correção:

| KPI | Antes (errado) | Depois |
|---|---|---|
| Ruptura de estoque | 460 itens / R$ 1.577.274,91 | **92 itens / R$ 287.768,76** |
| Produtos com cobertura curta | 653 de 891 | **129 de 891** |

Sobram **4.347 endereços físicos com saldo negativo** (ex.: H1401 −19.248).
Isso é inconsistência real de endereçamento e não é escondido: entra na soma
e sai na coluna `ENDERECOS_NEGATIVOS`. É sinal para o WMS, não para o PCP.

### O mínimo de cadastro não existe

`TGFEST.ESTMIN` está **100% zerado** em 2, 4 e 14 (31.631 linhas, nenhuma com
mínimo). Por isso "pouco estoque" é derivado do giro — saldo dividido pela
venda média diária de 90 dias. É melhor que o mínimo de cadastro: acompanha
sazonalidade sozinha, em vez de envelhecer numa tela que ninguém revisa.

---

## 6b. Estoque — a CODEMP 1 está corrompida

`TGFEST` por empresa:

| CODEMP | Linhas | Soma de ESTOQUE |
|---|---|---|
| 1 (produção) | **12.512.610** | **3,0 × 10¹⁹** ← inutilizável |
| 2 (CD) | 17.037 | 77.193.384 |
| 4 | 3.512 | **−248.978** |
| 14 (Extrema) | 11.089 | **−428.911** |

Além disso, `TGFEST.QTDPEDPENDEST` está **100% zerado** — a demanda tem que vir
de `TGFITE` sobre pedidos pendentes.

Com saldo do CD (CODEMP 2), a carteira viva de 45 dias tem 668 itens, dos quais
460 sem saldo, expondo R$ 1.577.274,91. **O número é alto demais para cobrar o
PCP sem calibração**: parte dele é transferência interna CD→produção, que a
skill de roteirização trata explicitamente como *não-ruptura*.

**Para destravar:** acordar com o PCP qual empresa é a fonte de saldo por linha
de produto, e separar ruptura real de transferência interna.

---

## 7. Reagendamento de entrega — o dado não existe de forma confiável

`AD_TSIAGENENT` está viva (555 registros em 30 dias). O domínio de `STATUS` tem
`M` = Mudança de Data — mas `M` aparece **1 vez em todo set/26**. A equipe
registra a mudança sobrescrevendo `NOVADATA`, sem marcar o status.

Usando `NOVADATA <> DTPREVENT` como proxy: 94 de 555 (16,9%). Só que **456 dos
555 pedidos (82%) não têm `DTPREVENT`**, então o proxy só avalia 99 casos — e
94 deles divergem. Isso mede preenchimento de cadastro, não o cliente empurrar
a entrega.

**Para destravar:** fazer a tela de agendamento gravar `STATUS='M'` quando a
data muda. É uma linha de regra, não um projeto.

**Enquanto isso**, `AD_TSIAGENENT.LIGAR` (preenchido em 3,8%) e `STATUS` em
`R`/`T` continuam úteis como lista de ligações — que é o entregável que a
skill de roteirização já define.

---

## 8. Ordens de carga — o número escondido

`TGFORD` está viva: 54 ordens em 21/09, média de 27,6/dia na semana.

Mas: **572 ordens de carga estão com `SITUACAO='A'` (aberta) há mais de 2
dias.** Esse é um número maior e mais incômodo que o ritmo diário, e nasceu
como coluna secundária do KPI. Vale uma conversa com a expedição sobre o que
significa — carga que nunca foi fechada no sistema, ou processo que não encerra.

---

## 9. Representantes — o número que parece ruim e não é

Com `TGFVEN.ATIVO='S'` e piso de relevância de R$ 5.000 de média trimestral:
53 representantes, **26 abaixo de 80%** da própria média, 16 abaixo de 50%,
7 zerados no mês.

No mesmo mês, o faturamento **total** projeta 107,7% da média.

Metade dos representantes cair enquanto o total sobe é mudança de mix (ou meta
individual desatualizada), não queda de esforço. Cobrar 26 pessoas com esse
número queima a credibilidade da matriz na primeira semana. Fica em sombra até
o diretor comercial fixar a meta individual.

Nota boa: **zero notas sem vendedor atribuído** no período — a distorção
clássica de ranking de comissão não está ocorrendo.

---

## 10. Fluxo de caixa — o buraco está em D+8, não em D+7

Títulos em aberto, não-provisão, Nitron, em 22/09/2026:

| Janela | A receber | A pagar | Saldo |
|---|---|---|---|
| D0–D7 | R$ 1.675.470,84 | R$ 1.817.828,24 | **−R$ 142.357,40** |
| D8–D30 | R$ 5.676.974,53 | R$ 13.426.196,66 | **−R$ 7.749.222,13** |

Vencido a receber (365 dias): **R$ 9.728.499,68** em 3.352 títulos.

O alerta de 7 dias quase não acusa nada. O de 30 dias acusa um gap de
R$ 7,7 milhões. **Por isso o KPI de fluxo mede as duas janelas** — um alerta
que só olha uma semana teria dado verde na véspera do problema.

### Saldo de abertura — limitação declarada

Isto é **compromisso a vencer**, não saldo de caixa: não inclui o saldo
bancário inicial. Para virar fluxo de caixa de verdade, somar o saldo de
`TGFCTA`/`TGFMOV`. Até lá, o número serve para medir **tendência e gap**, não
para dizer se a conta vira.


---

## 11. Fila de liberação — 155 pedidos parados, alguns há 6 meses

`TSILIB` é a fila de decisão. Pendente = `DHLIB IS NULL` **e**
`REPROVADO = 'N'`: quem foi reprovado saiu da fila, quem foi liberado tem
`DHLIB`; só os dois nulos são decisão não tomada.

Situação em 22/09/2026 (janela de 180 dias, tudo sobre `TGFCAB`):

| Evento | Descrição | Pendentes | Valor | Mais antigo |
|---|---|---|---|---|
| 9 | Tempo Inativo | 42 | R$ 264.488,21 | **139 dias** |
| 1004 | PIX — Aguardando Recebimento | 34 | R$ 185.710,07 | **180 dias** |
| 8 | Atraso | 29 | R$ 341.089,27 | 35 dias |
| 15 | Limite Créd. Mensal | 25 | R$ 260.468,33 | 32 dias |
| 3 | Limite de Crédito | 14 | R$ 153.931,06 | 32 dias |
| 13 | Valor Mínimo Tipo Negoc. | 4 | R$ 7.190,47 | 67 dias |
| 44 | Liberação exigida pela TOP | 3 | R$ 39.654,78 | 67 dias |
| 18 | Confirmação de Nota | 3 | R$ 664,95 | 7 dias |
| 12 | Frete CIF | 1 | R$ 7.985,95 | 0 dias |

**Total: 155 pedidos, R$ 1.261.183,09.**

Um pedido parado há 180 dias esperando confirmação de PIX não é fila — é
pedido que ninguém decidiu recusar. A matriz separa a fila em dois donos
(crédito → financeiro; o resto → comercial) e mede **dias do mais antigo**,
não a contagem: 30 pedidos parados há 2 dias é operação normal; 1 parado há
180 dias é dinheiro que já evaporou.

---

## 12. NTR Log — R$ 785 mil por mês de frete pago sem nota no ERP

**O maior número da apuração.**

NTR Log é `CODEMP 3` / `CODPARC 65253`: empresa do grupo **dentro** do recorte
Nitron (1,2,3,4,14,17,20), e por isso some nas consolidações que eliminam
intercompany. Foi assim que a lacuna passou despercebida.

Lado A — o que a Nitron lança como frete NTR (`TGFFIN`, natureza 9010107,
`RECDESP=-1`, não-provisão):

| Mês | Títulos | Valor lançado | Baixados (pagos) | Com `NUNOTA` |
|---|---|---|---|---|
| mar/26 | 680 | R$ 792.376,86 | R$ 765.841,31 | **0** |
| abr/26 | 708 | R$ 812.491,40 | R$ 783.000,00 | **0** |
| mai/26 | 534 | R$ 675.456,23 | R$ 655.494,90 | **0** |
| jun/26 | 571 | R$ 799.055,02 | R$ 769.733,97 | **0** |
| jul/26 | 552 | R$ 774.065,20 | R$ 747.617,81 | **0** |
| ago/26 | 636 | R$ 842.709,40 | R$ 821.142,28 | **0** |
| set/26 | 561 | R$ 600.449,66 | R$ 579.599,23 | **0** |

Lado B — o que a NTR Log emite (`TGFCAB`, `CODEMP 3`): **R$ 21 mil a R$ 29 mil
por mês**. Em agosto: R$ 21.567,12 contra R$ 842.709,40 pagos — cobertura de
**2,6%**, gap de R$ 821.142,28 no mês.

E não há NFS-e: `TGFNFSE` não tem nenhum registro para as empresas 1, 2, 3, 8,
14 ou 21 nos últimos 6 meses.

**O que isto prova:** o ERP registra despesa lançada e paga, todo mês, sem
nenhuma nota fiscal vinculada.
**O que isto NÃO prova:** que a nota não existe. Pode ter sido emitida na
prefeitura e nunca importada para o ERP. Essa é exatamente a pergunta que a
ação do KPI manda o financeiro responder — por isso ela pede a **conciliação**,
não a conclusão.

---

## 13. Devedores que continuam comprando

Consolidando por `TGFPAR.CODPARCMATRIZ` (filial que deve e matriz que compra
são o mesmo risco), com piso de R$ 50 mil:

- **14 devedores** somando **R$ 1.804.739,47** vencidos
- **7 deles ainda comprando**
- A Nitron faturou **R$ 1.511.887,35 para devedores** nos últimos 30 dias

Os casos que explicam o KPI:

| Cliente | Deve | Atraso | Comprou em 30d |
|---|---|---|---|
| 001 - INTERLAGOS - SP | R$ 418.413 | 286 dias | **R$ 563.204** |
| KALUNGA SA | R$ 253.176 | 30 dias | **R$ 366.993** |
| TUBARAO 65 | R$ 284.404 | 120 dias | — |
| VINICIUS MASSARU KATO | R$ 102.891 | 150 dias | R$ 5.095 |

Por isso a métrica do KPI é **"ainda comprando"**, não o valor devido: devedor
que parou de comprar é caso de cobrança; devedor que continua comprando é
falha de bloqueio, e a ação é outra — travar o crédito, não ligar de novo.

---

## 14. Gastos fora do padrão

Comparando cada `CODNAT` de despesa em ago/26 contra a própria média de 12
meses (piso de relevância R$ 50 mil de média mensal):

| Natureza | Mês fechado | Média 12M | % |
|---|---|---|---|
| Emprestimos e Financiamentos | R$ 4.678.714 | R$ 1.763.563 | **265%** |
| Injeção Tercerizada | R$ 578.941 | R$ 309.947 | 187% |
| Embalagens | R$ 274.954 | R$ 149.942 | 183% |
| Adiantamento a Fornecedores | R$ 485.055 | R$ 347.260 | 140% |
| Lucros e Dividendos Distribuidos | R$ 796.227 | R$ 583.610 | 136% |
| Devoluções de vendas | R$ 350.774 | R$ 267.292 | 131% |

**8 naturezas estouradas, R$ 3.810.939,21 acima do padrão.**

### Por que a razão despesa/faturamento fica em sombra

A despesa bruta da `TGFFIN` roda entre R$ 10,6 mi e R$ 15,2 mi por mês contra
faturamento de R$ 7,5 mi — a razão passa de **190%**, e isso não significa
prejuízo: os dois lados não são comparáveis. A despesa inclui matéria-prima,
empréstimos, dividendos, impostos e movimento entre as 7 empresas do recorte;
o faturamento usa a âncora `ATUALCOM='C'`, que é só receita de venda.

**Para ativar:** a controladoria define quais naturezas compõem "despesa
operacional" (fora 4010203 Empréstimos, 7010101 Dividendos, 8010700
Adiantamentos e as de imposto). Só então o percentual significa alguma coisa.

---

## 15. Produtos que pararam de vender

90 dias contra os 90 anteriores, por produto, em valor, contando só quem
**tinha** performance no período base (piso de R$ 20 mil — sem ele a cauda
longa inunda a lista):

- 1.071 produtos com movimento
- **129 em queda acima de 30%**, 70 acima de 50%, 7 pararam de vender
- **R$ 3.921.906,88** a menos do que o mesmo conjunto gerava antes

Os cinco maiores:

| Produto | Antes | Agora | Restou |
|---|---|---|---|
| LIXEIRA RATTAN COM PEDAL - BRANCA 6L | R$ 285.623 | R$ 135.219 | 47% |
| GAVETEIRO COM 4 GAVETAS - PRETA | R$ 218.368 | R$ 94.631 | 43% |
| PORTA PAO ARMAZENA E CONSERVA 2,7L | R$ 168.234 | R$ 86.764 | 52% |
| PORTA FRIOS COM PINCA 1,1L | R$ 152.851 | R$ 75.622 | 49% |
| ESCORREDOR DE PRATOS - PRETO | R$ 136.950 | R$ 47.446 | 35% |

---

## 16. Teak Brazil — uma das duas empresas nunca emitiu

`CODEMP 8` (São Paulo) e `CODEMP 21` (Rondônia), mesma razão social, fora do
recorte Nitron — não aparecem em nenhum outro KPI.

| Mês | Notas (CODEMP 8) | Valor |
|---|---|---|
| mar/26 | 5 | R$ 119.537,71 |
| abr/26 | 2 | R$ 272.792,00 |
| mai/26 | **1** | R$ 19.830,40 |
| jun/26 | 11 | R$ 240.806,91 |
| jul/26 | 13 | R$ 298.119,32 |
| ago/26 | 18 | R$ 321.095,22 |
| set/26 | 10 | R$ 170.882,56 |

**CODEMP 21 (Rondônia): zero emissão em 6 meses.**

A métrica do KPI é **dias sem emitir**, não o valor: o padrão da Teak é
irregular por natureza (1 nota em maio, 18 em agosto), então cobrar variação
de valor dispararia alarme toda semana. O que é anômalo é o silêncio — maio
teve uma nota só, e isso deveria ter sido percebido na época.
