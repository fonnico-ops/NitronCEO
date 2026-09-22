# Governança da matriz

O software é a parte fácil. O que faz o cérebro funcionar — ou virar ruído que
todo mundo aprende a ignorar em três semanas — está aqui.

---

## A regra que sustenta tudo

**Um KPI só entra na matriz se alguém puder ser cobrado por ele.**

Se a resposta à pergunta "quem resolve isso?" for "depende", "o time" ou
"a diretoria", o indicador não está pronto. Vira dashboard. Dashboard é
legítimo — só não é isto.

---

## Os quatro campos obrigatórios

| Campo | Pergunta que responde | Se estiver errado |
|---|---|---|
| `sql` + `metrica` | O que eu meço? | O número não é auditável |
| `avaliacao` | Quando isso é problema? | Alerta dispara sempre ou nunca |
| `dono` | Quem resolve? | A cobrança não chega em ninguém |
| `acao.passos` | O que ele faz? | A resposta vem como "estou olhando" |

---

## Modo sombra existe para proteger a credibilidade

Um KPI em `modo: sombra` mede, grava e aparece no pulso do CEO — mas **não
notifica ninguém**.

É para isto que serve: um alerta errado custa mais que um alerta ausente. Se a
expedição for cobrada por um reagendamento que na verdade é campo em branco no
cadastro, ela aprende em uma semana que a matriz erra — e a partir daí ignora
também os alertas certos.

**Um KPI sai da sombra quando:** o dado de origem foi corrigido ou
instrumentado, E a área dona concordou com o limiar.

Hoje, 5 dos 13 estão em sombra. Os motivos de cada um estão em
[`achados-de-dados.md`](achados-de-dados.md).

---

## Um papel pode ser duas pessoas

Faturamento/Expedição são duas (Expedição e Forla Silva); Produção e
Qualidade são as mesmas duas (Alex Souza e Charles Silva).

Quando um papel tem duas pessoas, **as duas recebem a mesma cobrança**. O
motor não escolhe uma nem divide o pedido entre elas: o dono é o papel, e
dividir a cobrança a transformaria em cobrança de ninguém.

Produção e Qualidade continuam papéis separados mesmo apontando para as
mesmas pessoas hoje. São KPIs diferentes, prazos diferentes e conversas
diferentes — e se amanhã a qualidade ganhar dono próprio, basta trocar o
endereço.

---

## A escada de cobrança

```
ação aberta
   │
   ├─ prazo (SLA do KPI)         → lembrete ao dono, no Teams
   ├─ prazo + 50%                → escala ao gestor do dono, Teams + e-mail
   ├─ prazo × 2                  → escala ao CEO
   └─ depois disso               → para de cobrar; vira pauta de reunião
```

Hoje todos os papéis escalam direto para o CEO, porque a hierarquia
intermediária não foi declarada. Isso significa que a segunda rodada já chega
no Renato. Cada `escalonar_para` intermediário que for preenchido é um
assunto operacional a menos na mesa dele.

**Por que para na terceira rodada:** cobrança que se repete para sempre deixa
de ser cobrança. Se três avisos e duas escaladas não produziram resposta, o
problema não é o indicador nem o processo — é de gente, e se resolve numa
conversa, não por mensagem automática.

`nível crítico` corta o prazo pela metade (piso de 1 hora). É a única diferença
de tratamento entre vermelho e crítico.

---

## Reincidência

O motor conta dias consecutivos em nível vermelho. A partir do **terceiro dia
seguido**, a mensagem muda de tom:

> ⚠️ 3º dia seguido neste nível. Não é um dia ruim — é uma tendência, e a
> resposta precisa tratar a causa.

Isso existe porque a resposta aceitável no dia 1 ("cliente adiou") deixa de ser
aceitável no dia 3.

---

## Onde a resposta é dada

A resposta acontece **na própria cobrança, no painel** — não num e-mail de
volta que ninguém arquiva. Quem abre a cobrança vê a pergunta, o que foi
pedido, os números e a base do cálculo, e escreve ali.

Há duas formas de responder, e a diferença importa:

| Gesto | O que acontece |
|---|---|
| Responder | fica registrado, assinado e visível. O SLA **continua correndo**. |
| Responder marcando *"isto encerra a cobrança"* | a escada para. |

Isso existe porque "estou olhando" é uma resposta legítima e não é uma
conclusão. Separar as duas evita a situação em que a cobrança some da lista
porque alguém digitou qualquer coisa.

A resposta fica na base do painel; `nitronceo importar` traz as encerradas
para o banco local e fecha a ação.

---

## Uma ação por KPI por dia

O identificador da ação é `sha1(kpi_id + data)`. Rodar o motor quatro vezes no
mesmo dia atualiza a ação existente; não abre quatro.

Quem recebe quatro mensagens do mesmo assunto para de ler todas — inclusive a
que importava.

---

## Rituais

| Quando | O quê | Quem |
|---|---|---|
| 07:00 | Fluxo de caixa D0–D30 | Financeiro |
| 07:30 | Pulso diário (faturamento, pedidos, cargas, devoluções, ruptura) | Donos das áreas |
| de hora em hora | Injetoras paradas | Gerente de produção |
| Segunda 08:00 | Semanal (representante, canal, reentradas, inadimplência) | Diretoria |
| Segunda 09:00 | Reunião sobre o que não foi respondido na semana | CEO |

A reunião de segunda é parte do desenho, não um extra. É o degrau que existe
**depois** que a escada automática para.

---

## O que este sistema não faz

Vale dizer em voz alta, porque a expectativa errada mata a ferramenta:

- **Não decide.** Ele pergunta, com número e prazo. A decisão é de gente.
- **Não substitui o dashboard.** Números de consulta continuam no cockpit.
- **Não garante que o dado está certo.** Garante que a metodologia do número
  está declarada e versionada — o que é diferente, e é auditável.
- **Não mede o que a Nitron não instrumenta.** Setup de molde é o exemplo:
  nenhum modelo compensa uma medição que parou em outubro de 2024.
