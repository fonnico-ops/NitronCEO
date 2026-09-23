# Pedido à TI — permissões para o NitronCEO enviar e ler cobranças

> Documento para encaminhar à TI / ao administrador do Microsoft 365.
> Dúvidas técnicas: este repositório, `docs/arquitetura.md`.

---

## 1. O que é

O **NitronCEO** é um sistema interno que lê o ERP Sankhya (somente leitura),
compara 37 indicadores com os limiares definidos por área, e quando um deles
sai da linha abre uma ação com dono e prazo e envia a cobrança por e-mail.
Se a pessoa não responde, ele cobra de novo e escala — no máximo três vezes.

Ele roda sem interação humana, num agendamento (cron), num servidor da
empresa. Por isso precisa de uma identidade própria de aplicação; não pode
depender de alguém estar com o Outlook aberto.

## 2. O que estamos pedindo

Um **registro de aplicativo** no Entra ID (app registration) com
autenticação por client credentials (client ID + secret), com **duas
permissões de aplicação** no Microsoft Graph:

| Permissão | Tipo | Para quê |
|---|---|---|
| `Mail.Send` | Aplicação | enviar a cobrança |
| `Mail.Read` | Aplicação | ler a resposta que a pessoa manda de volta |

E **uma restrição de escopo**, que é a parte que nos importa tanto quanto a
permissão em si (§3).

A caixa que assina as cobranças será:

```
renato.fonseca@nitron.com.br
```

O `Mail.Read` é o que fecha o ciclo: quando a pessoa responde o e-mail da
cobrança, o sistema precisa ler essa resposta para parar de cobrar. Sem
ele, quem responde continua sendo cobrado — o que inutiliza o sistema em
duas semanas.

## 3. A restrição — por favor, não conceda sem ela

`Mail.Send` e `Mail.Read` de aplicação são, por padrão, **amplos**: dão ao
app acesso a *todas* as caixas do tenant. Não é isso que precisamos, e não é
isso que queremos.

Pedimos que seja aplicada uma restrição de escopo limitando o app a **uma
única caixa**. Caminho clássico, via Exchange Online PowerShell:

```powershell
# 1. Grupo de segurança habilitado para email, com um único membro
New-DistributionGroup -Name "NitronCEO-Caixa" `
  -Type Security `
  -PrimarySmtpAddress nitronceo-caixa@nitron.com.br `
  -Members renato.fonseca@nitron.com.br

# 2. O app só enxerga as caixas desse grupo, e de mais nenhuma
New-ApplicationAccessPolicy `
  -AppId <CLIENT_ID_DO_APP> `
  -PolicyScopeGroupId nitronceo-caixa@nitron.com.br `
  -AccessRight RestrictAccess `
  -Description "NitronCEO - cobrancas automaticas"

# 3. Conferir
Test-ApplicationAccessPolicy `
  -Identity renato.fonseca@nitron.com.br -AppId <CLIENT_ID_DO_APP>
Test-ApplicationAccessPolicy `
  -Identity <qualquer.outra.pessoa>@nitron.com.br -AppId <CLIENT_ID_DO_APP>
```

O terceiro passo é o que importa: o primeiro `Test-` tem que devolver
**Granted** e o segundo, **Denied**.

**Observação:** a Microsoft tem migrado esse controle para *RBAC for
Applications* (`New-ManagementRoleAssignment -App ...`, com escopo de
aplicação). Se o tenant já estiver nesse modelo, ou se o
`New-ApplicationAccessPolicy` estiver indisponível na sua versão, use o
equivalente em RBAC — o requisito é o resultado, não o comando: **o app só
pode alcançar uma caixa**.

## 4. O que o app NÃO precisa, e não deve receber

Para evitar que o pedido seja aprovado com mais do que o necessário:

- ❌ `Mail.ReadWrite` — ele não altera, move nem apaga e-mail
- ❌ `Mail.Send` sem restrição de escopo
- ❌ `User.Read.All`, `Directory.Read.All` — não lê o diretório
- ❌ `Files.*`, `Sites.*` — não toca em SharePoint nem OneDrive
- ❌ Qualquer permissão de Teams — **nesta fase** (ver §7)

## 5. O que a TI vai querer saber

**Onde rodam as credenciais.** Em servidor da empresa, como variáveis de
ambiente (`MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`,
`MS_REMETENTE`). Não vão para o repositório de código — `.env` está no
`.gitignore`.

**Que dado sai da empresa.** Nenhum e-mail sai. O conteúdo das cobranças é
gerado a partir do Sankhya e enviado dentro do próprio tenant, para caixas
`@nitron.com.br`. As respostas são lidas e gravadas num banco local
(SQLite) no mesmo servidor.

**Para quem o app escreve.** Somente para os donos de cobrança declarados
em `config/pessoas.yaml`, hoje 9 pessoas de 9 áreas. Não há envio para
fora do domínio, e não há lista dinâmica: quem não está no arquivo não
recebe nada.

**Quanto ele lê.** Somente a caixa autorizada, e somente mensagens dos
últimos 30 dias cujo **assunto contenha o token** `[NTR-xxxxxxxx]` gerado
por ele mesmo. Todo o resto é descartado sem ser gravado.

**O que acontece se o secret vazar.** Com a restrição do §3, o dano fica
contido a uma caixa. Sem ela, seria o tenant inteiro — por isso insistimos
na restrição.

**Rotação.** Sugerimos secret com validade de 12 meses e lembrete de
renovação; o sistema falha de forma visível (a rodada registra o erro) se
o secret expirar, não silenciosamente.

## 6. Como testar que funcionou

Depois do consentimento, do nosso lado:

```bash
nitronceo rodar --canais email --kpi emissao_ntrlog
nitronceo respostas
```

O primeiro comando envia uma cobrança real. O segundo lê a caixa e mostra
se a resposta foi amarrada à ação. Se algo faltar, o erro aponta a
permissão exata que está faltando.

## 7. Fase 2 — Teams (não é para agora)

Quando o e-mail estiver rodando, queremos avaliar o Teams. Registramos
desde já que **não** estamos pedindo isso agora, e que entendemos por que
é mais sensível: mandar mensagem direta 1:1 por permissão de aplicação
exige `Chat.Create` + `ChatMessage.Send`, que dão ao app o direito de
abrir conversa com qualquer pessoa da empresa, sem restrição de escopo
equivalente à do §3.

Se e quando chegarmos lá, a alternativa que preferimos avaliar primeiro é
um **Incoming Webhook** por canal — uma URL criada dentro do próprio canal
do Teams, que **não precisa de consentimento no Entra** e posta com nome e
avatar próprios. Cobre o aviso de time; não cobre a mensagem individual.

---

## Resumo em uma linha

Um app registration com `Mail.Send` + `Mail.Read` de aplicação,
**restrito a `renato.fonseca@nitron.com.br` por
ApplicationAccessPolicy** (ou o equivalente em RBAC for Applications).
