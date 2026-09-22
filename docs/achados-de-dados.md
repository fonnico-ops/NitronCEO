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

## 3. Setup de máquina — RESOLVIDO: a fonte certa é `TPRIWC`

**Correção de 22/09/2026, à noite.** Tudo o que esta seção dizia abaixo
estava certo sobre as fontes que eu tinha olhado, e errado sobre a conclusão:
a parada É medida, só não onde eu procurei.

`TPRIWC` guarda os intervalos de parada do centro de trabalho, com
`AD_CODMTP` apontando para `TPRMTP` (cadastro de motivos). Está **viva**:
80.308 linhas, última gravação em 22/09/2026 18:28, 3.066 paradas nos
últimos 30 dias, 13 abertas naquele momento.

Motivos dos últimos 30 dias, por tempo total:

| Cód | Motivo | Tipo | Paradas | Minutos | Média |
|---|---|---|---|---|---|
| — | **(sem motivo)** | — | **1.791** | **386.411** | 216 |
| 30 | LIBERADO | — | 757 | 323.064 | 427 |
| 10 | **SETUP** | S | 218 | 71.527 | 328 |
| 7 | Manutenção de máquina | C | 74 | 61.849 | 836 |
| 6 | **Manutenção de molde** | C | 69 | 46.397 | 672 |
| 13 | Refeição | — | 124 | 29.744 | 240 |
| 2 | Falta de operador | — | 19 | 19.399 | 1.021 |
| 14 | Falta de matéria-prima | — | 12 | 1.561 | 130 |
| 3 | Preparador | — | 2 | 32 | 16 |

Isso destravou quatro coisas de uma vez:

- **Setup saiu da sombra.** 217 setups fechados em 30 dias, **mediana de
  115,8 min contra padrão de 40**, apenas 25% dentro do padrão, **711,8 horas
  perdidas**. A pior é a INJETORA 19: mediana de 496 min em 15 trocas.
- **Máquinas paradas ganharam o motivo.** O KPI dizia *que* parou; agora diz
  *por quê*, que sempre foi a pergunta da cobrança.
- **Projetos/Moldes ganhou seu primeiro KPI.** 773 horas de injetora parada
  por molde em 30 dias, 30 máquinas afetadas.
- **Apareceu um indicador sobre o indicador:** 58% das paradas não têm motivo.

### Mediana, não média

A média de setup dá 329 min; a mediana dá 116. A diferença são 8 paradas
acima de 24 horas (a maior tem 5.459 min = 91 h) — apontamento que ficou
aberto atravessando turno e fim de semana, não troca de molde. Elas saem do
cálculo e são contadas à parte: é problema de apontamento, e apontamento e
setup se resolvem com gente diferente.

### Refeição não é problema

8 das 13 paradas abertas às 18:30 eram refeição. Contá-las dispararia alerta
todo dia no mesmo horário. Saem do número principal; refeição acima de 90 min
vira contagem separada, porque aí não é refeição — é apontamento que ninguém
fechou.

### O que eu tinha concluído antes (mantido como registro)



O padrão existe: `TPRWCP.TEMPOSETUP` = 40 min nas 45 injetoras.
O realizado não é gravado desde 31/10/2024.

Tentamos inferir o setup pela lacuna entre o último apontamento de ciclo de uma
OP e o primeiro da OP seguinte na mesma injetora. Resultado medido (7 dias):

```
102 lacunas | média 6 min | MEDIANA 2 MIN | 6,9% acima de 40 min
```

**Mediana de 2 minutos não é troca de molde.** A lacuna está medindo troca de
`NUCICLO` sem parada física. A aproximação não serve.

Essa conclusão caiu: a instrumentação existia o tempo todo em `TPRIWC`. Fica
o registro de que a aproximação por lacuna entre OPs **não serve** — se
alguém tentar de novo, dá mediana de 2 minutos.

Lição para o resto da matriz: "o dado não existe" quase sempre quer dizer "eu
não achei o dado". Antes de declarar um KPI impossível, vale perguntar a quem
opera onde ele é gravado.

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


---

## 17. A meta de R$ 500 mil/dia e a agenda que não cabe nela

Regra de negócio dada pela diretoria em 22/09/2026: **R$ 500 mil por dia
útil, nas empresas 1, 2, 4 e 14** — e o mesmo número vale para faturar e para
carregar, porque a fábrica escoa na mesma capacidade.

### Onde a operação está contra a meta

Últimos 63 dias úteis nas empresas 1, 2, 4 e 14:

| | |
|---|---|
| Média por dia | R$ 364.278 |
| Mediana | R$ 329.452 |
| Mínimo | R$ 43.918 |
| Máximo | R$ 1.295.895 |
| Dias que bateram R$ 500 mil | **11 de 63 (17,5%)** |

A meta está **37% acima da média realizada**. Isso é escolha de gestão, não
erro de cálculo — mas o KPI nasce vermelho e continua vermelho até a operação
mudar. Por isso os limiares dele foram afrouxados (85/70 em vez de 92/85):
para que "vermelho" continue significando alguma coisa.

### A agenda de carga: 2 dias estourados, 9 ociosos

Próximos 15 dias úteis, por `TGFORD.DTPREVSAIDA`:

| Dia | Agendado | |
|---|---|---|
| 02/10 | R$ 1.875.158 | **3,8× a capacidade**, 28 ordens todas abertas |
| 22/09 | R$ 840.451 | 1,7× a capacidade, 19 ordens abertas |
| 23/09 | R$ 196.109 | ocioso |
| 24/09 | R$ 151.456 | ocioso |
| 25/09 | R$ 154.165 | ocioso |
| 28/09 | R$ 115.742 | ocioso |
| 29/09 | R$ 37.728 | ocioso |
| 30/09 | R$ 79.457 | ocioso |
| 01/10 | R$ 0 | ocioso |
| 05/10 | R$ 136.053 | ocioso |
| 06/10 | R$ 116.773 | ocioso |

**R$ 1.715.609,62 precisam sair das datas que estouram; R$ 3.512.518,91 de
capacidade estão parados nos outros dias.** O problema não é falta de carga —
é distribuição.

Mais 58 ordens **abertas** com data prevista vencida há mais de 30 dias:
carga que nunca saiu e ninguém fechou.

> Armadilha que eu mesmo caí: contar "datas absurdas" sobre a TGFORD inteira
> dá 22.990 — mas 26.632 ordens FECHADAS têm data vencida, e isso é histórico
> normal. O número acionável são as **abertas**.

### A carteira não é o gargalo

727 pedidos na carteira roteirizável (45 dias, sem ordem de carga),
R$ 2.229.298,53, dos quais **R$ 2.011.711,42 com estoque = 4,0 dias de
meta**. Só R$ 217.587 sem estoque.

Isso fecha o raciocínio: com 4 dias de meta na mão e a capacidade ociosa em 9
dos próximos 11 dias agendados, **quando o dia não bate R$ 500 mil o gargalo
não é falta de pedido nem falta de estoque — é a distribuição da agenda.**


---

## 18. Capital parado e capacidade perdida

### R$ 607 mil em produto inativo — e 83% é um item só

57 produtos com `TGFPRO.ATIVO='N'` ainda têm saldo: 304.723 unidades,
R$ 607.635,72 a custo médio. Mas a distribuição é o que importa:

| | Valor | Produtos |
|---|---|---|
| **CESTO ORG. VERSÁTIL LAVANDERIA-FSC** | **R$ 502.074** | 1 (253.036 un, zero venda em 180d) |
| Demais sem venda em 180 dias | R$ 37.883 | 42 |
| Ainda vendem (liquidáveis com desconto) | R$ 67.679 | 14 |

Não são 57 produtos para resolver — é **um produto e 56 acompanhantes**. A
ação separa as duas conversas porque são decisões diferentes: o que ainda
vende sai com desconto; o que não vendeu nada é baixa, não promoção.

8 dos 57 não têm custo cadastrado e entram com zero, então o total real é um
pouco maior.

### Um item com 78 milhões de unidades em estoque

Ao valorizar o estoque ATIVO o total deu **R$ 445 milhões**, o que não é
plausível para a operação. A causa: `CODPROD 6639` ("POTE ACOPLADO COM COPO
MEDIDOR") aparece com **78.067.352 unidades**, R$ 419 mi sozinho. Sem ele, o
estoque ativo fica em ~R$ 26 mi, que é a ordem de grandeza esperada.

Isso não afeta o KPI de inativos (o 6639 está ativo), mas contamina qualquer
valorização de estoque e merece correção no cadastro.

### Ciclo de injeção 28% acima do padrão

`AD_TGPAPO.CICLOREAL` contra `CICLOBASE`, 30 dias, 276.713 apontamentos
válidos:

- **Mediana em 128,5% do ciclo base** — metade da produção roda 28% mais lenta
- 146.881 apontamentos acima de +25%; 63.020 acima de +50%
- **10 das 45 injetoras** com mediana acima de 140%

| Injetora | Base | Real | |
|---|---|---|---|
| 7 | 18,0s | 32,4s | **178%** |
| 22 | 18,8s | 30,6s | 162% |
| 2 | 19,0s | 34,3s | 160% |
| 44 | 20,0s | 25,7s | 155% |
| 9 | 16,8s | 27,8s | 154% |

Ciclo alto é perda **silenciosa**: a máquina está ligada, o apontamento
acontece, ninguém reclama — e a fábrica entrega menos peça por hora do que a
programação assumiu. Diferente da parada, que salta aos olhos.

Cruzamento que vale a reunião: a **INJETORA 19** está a 140% de ciclo **e** é
a pior em tempo de setup (mediana de 496 min em 15 trocas). Mesma máquina,
dois problemas.

**Ressalva de leitura:** ciclo base alto demais no cadastro esconde o
problema; base baixa demais inventa um. 14.756 apontamentos sequer têm
`CICLOBASE` e ficam fora da conta. Máquina muito fora da curva pede
conferência do cadastro antes da cobrança — está escrito nos passos da ação.


---

## 19. Ordens de serviço: 503 abertas, 7 delas com menos de uma semana

`AD_TGFMANUT` é a ordem de serviço de manutenção e está viva — 12.310 OS, a
última aberta em 22/09/2026. Aberta = `TERMSERV IS NULL`.

| Tipo | Abertas | Idade mediana | Acima de 180d | Equip. parado |
|---|---|---|---|---|
| INDUSTRIAL | 222 | **133 dias** | 71 | 184 |
| PREDIAL | 168 | **171 dias** | 77 | 108 |
| MOLDES | 108 | 93 dias | 13 | 34 |
| GEN | 5 | 22 dias | 1 | 4 |

**503 abertas, 483 com mais de 30 dias, e só 7 com menos de uma semana.** A
mais antiga tem 602 dias.

### O contraste que muda a leitura

Quem fecha, fecha rápido. Nos últimos 365 dias foram 1.804 OS fechadas com
mediana de **0,8 dia** (MOLDES 0,7 · INDUSTRIAL 1,8 · PREDIAL 4,4 · GEN 13,1).

Então o problema **não é velocidade de execução**. São duas outras coisas: a
cauda (140 das 1.804 levaram mais de 30 dias) e o acúmulo de um backlog que
ninguém fecha.

### 330 equipamentos parados há meses — ou OS que ninguém fechou

330 das 503 OS abertas dizem `PARADO = 'SIM'`, várias há mais de um ano. É
implausível que 330 equipamentos estejam parados há meses numa fábrica que
está produzindo. O número quase certamente mistura **serviço realmente
pendente** com **OS executada e nunca fechada no sistema**.

Os dois são problema — um de manutenção, outro de disciplina de processo — e
o primeiro passo da ação é separá-los. É o mesmo padrão das 58 ordens de
carga abandonadas.

### Dois campos que não servem para agrupar

- **`PRIORIDADE` perdeu o sentido:** 10.460 das 12.310 OS (85%) estão
  `URGENTE`. Quando tudo é urgente, nada é — por isso a métrica do KPI não
  usa prioridade.
- **`LOCAL` é texto livre** com cinco grafias de "ferramentaria"
  (`FERRAMENTARIA`, `ferramentaria`, `Ferramentaria`, `FERRAMEMTARIA`,
  `"FERRAMENTARIA ."`). Só entra normalizado em maiúsculas.

### 90% da manutenção é corretiva

`TIPOMANUT` na base histórica completa: **CORRETIVA 11.090 (90,1%)**,
PREVENTIVA 1.220 (9,9%). Nos últimos 180 dias está **pior**: 7% (72 de
1.022), com INDUSTRIAL em 5%.

Isso explica parte de dois outros KPIs desta matriz — `manutencao_molde` (773
horas de injetora parada por molde em 30 dias) e `ciclos_altos` (mediana em
128,5% do ciclo base). Máquina que só recebe atenção depois de quebrar roda
mais devagar antes de quebrar.

### Uma segunda fila, sem dono

`AD_TGFCHAMADOS` (chamados de sistema, com `MODULO` e `STATUSCHAMADO`)
também está viva: 3.084 chamados, **542 abertos**, última em 21/09/2026. Não
virou KPI porque não há papel de TI declarado em `pessoas.yaml`.


---

## 20. Canhoto: a frota própria não devolve, a transportadora devolve

A prova de entrega vive em **`AD_ARQENTREGA`**, chaveada por `NUNOTA` —
66.993 arquivos em 65.394 notas. A tabela não estava no dicionário; foi
encontrada lendo a definição da view `AD_VW_TITREC_NF`, que já calculava
`TEMCANHOTO` para a fila de títulos a receber.

Nos últimos 90 dias (empresas 1, 2, 4 e 14): 16.106 notas faturadas, **18,7%
com canhoto**. 9.478 notas com mais de 15 dias e sem comprovante, somando
**R$ 3.996.797,59**.

### O corte que dirige a cobrança

| Mês | Entrega própria / NTR | Transportadora terceira |
|---|---|---|
| abr/26 | 15,0% (3.862 notas) | 65,8% (1.421 notas) |
| mai/26 | 9,0% (5.012) | 65,0% (1.330) |
| jun/26 | 8,2% (5.194) | 68,8% (828) |
| jul/26 | 13,1% (3.651) | 62,7% (773) |
| ago/26 | 9,5% (4.395) | 60,6% (1.059) |

Quando a mercadoria vai por transportadora de terceiro, o canhoto volta em
**6 de cada 10** entregas. Pela frota própria/NTR Log, volta em **1 de cada
10** — e a frota é **quatro vezes o volume**.

Não é problema de sistema: é o processo de retorno do canhoto da entrega
própria. E conecta com `emissao_ntrlog` — a mesma operação que não emite nota
de frete também não devolve comprovante de entrega.

Concentração do risco: **NATURA FILIAL CABREÚVA, 6 notas, R$ 1.136.353** sem
canhoto. Depois HYAK (R$ 567.074) e CASA E VIDEO (R$ 244.284).

### O status de entrega não existe na prática

`TGFCAB.AD_STATUSENTREGA` existe como campo e está **100% NULO** nas 16.497
notas de venda dos últimos 90 dias. Não há como monitorar status de entrega
porque ninguém preenche.

Isso deixa uma lacuna real: hoje só dá para saber se a entrega foi
**comprovada** (canhoto), não em que **estágio** ela está. Preencher esse
campo — ou apontar o estágio em outro lugar — é o que permitiria um KPI de
entrega em andamento, e não só de entrega provada.

### Uma segunda fila de comprovação

A mesma view mostra `TEMXML` e `TEMDANFE`: dos 20.300 títulos a receber em
aberto, 6.931 (34%) têm XML e DANFE amarrados. Não virou KPI, mas é a mesma
família de problema — documento que deveria estar anexado e não está.


---

## 21. E-commerce: não há flag de canal, e a integração de marketplace é nova

### Como o e-commerce é identificado

Não existe marcador de canal para e-commerce. `TGFCAB.AD_ORIGEM` tem
Representante, Força de Vendas, Farmer, Gestor e Outside — e-commerce não
está entre eles. A identificação é pela **TOP**, cuja descrição contém
"Site":

| TOP | Descrição | Notas em 180d |
|---|---|---|
| 3226 | Venda Site Mundo Ud | **21.506** (R$ 523.322) |
| 3248 | Venda Site Nitron Clientes Especiais | 2 |
| 3231 | Venda Site Hyak | 0 |
| 3232 | Venda Site FULL ML | 0 |

Ou seja: na prática o e-commerce faturado é **uma TOP só**. Existe "Pedido de
Venda Site Nitron" (3127) com 3.621 pedidos em 180 dias, mas não há TOP de
faturamento correspondente com movimento — vale conferir por onde esses
pedidos faturam.

### O ritmo, e o que o ticket revela

| Mês | Pedidos | Valor | Ticket |
|---|---|---|---|
| abr/26 | 3.153 | R$ 79.405 | R$ 25,18 |
| mai/26 | 3.805 | R$ 83.578 | R$ 21,97 |
| jun/26 | 3.894 | R$ 87.309 | R$ 22,42 |
| jul/26 | 3.096 | R$ 83.638 | R$ 27,01 |
| ago/26 | 4.043 | **R$ 126.937** | **R$ 31,40** |
| set/26 (22d) | 3.257 | R$ 84.901 | R$ 26,07 |

O mês corrente roda a **154,7% da média de 90 dias** — está crescendo. Mas o
ticket caiu de R$ 28,34 (histórico) para R$ 26,07: o crescimento é por
**volume de pedido barato**, não por ticket. Por isso o KPI traz os dois.

### A quebra por plataforma só existe desde 31/08

`AD_PEDIDOSANY` é a integração Anymarket e traz `MARKETPLACE` e
`ACCOUNTNAME`. É **nova**: primeiro pedido em 31/08/2026 (Shopee Mundo UD),
14/09 (Mercado Livre Mundo UD), 16/09 (Shopee Nitron).

| Marketplace / conta | Pedidos | Valor | Taxa |
|---|---|---|---|
| SHOPEE / Mundo UD | 1.091 | R$ 19.850 | R$ 0 |
| SHOPEE / Nitron | 559 | R$ 9.070 | R$ 0 |
| MERCADO_LIVRE / Mundo UD | 172 | R$ 7.643 | R$ 853 |
| MERCADO_LIVRE / Nitron Vida Casa | 23 | R$ 1.049 | R$ 134 |

**Dos 1.845 pedidos do Anymarket, só 1.115 (60%) têm `NUNOTA`** — 40% não
viraram nota. Pode ser fila normal de processamento ou falha de integração; é
pergunta na ação do KPI.

A taxa da Shopee aparece como zero, o que provavelmente significa que não
está sendo importada — o custo real do marketplace não está no ERP.

### A cauda do catálogo

90 dias, 382 SKUs vendidos, R$ 309.402:

- **90 SKUs (23,6%) fazem 80% da receita**
- **120 SKUs venderam menos de R$ 100** no trimestre, somando R$ 5.700 —
  1,8% da receita em 31% do catálogo ativo
- 83 SKUs venderam até 2 unidades

Concentração alta é normal no varejo online; o que se cobra é a decisão sobre
a cauda, porque cada SKU custa foto, descrição, anúncio em cada marketplace e
espaço de estoque.
