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

## 6. Estoque — a CODEMP 1 está corrompida

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
