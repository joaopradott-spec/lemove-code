# Lemove Code

Terminal bonito, estilo **OpenCode** / **Claude Code**, que usa o **Claude
Desktop de graça** como cérebro — sem precisar de API paga.

Depois de instalado, digitar `lemovecode` em qualquer `cmd.exe` ou
PowerShell abre a interface, de qualquer pasta — exatamente como o
comando `opencode` funciona no projeto original.

---

## 1. Instalação

Precisa de **Python 3.9+** e **Node 18+** no Windows.

### Opção A — instalador (recomendado)

Dê duplo clique em **`instalar.bat`**. Ele faz tudo sozinho:

1. Confere Python e Node.
2. Instala o comando `lemovecode` (`pip install -e .`).
3. Instala as dependências do servidor MCP (`npm install`).
4. Registra o MCP `lemove-code` no Claude Desktop (sem apagar sua config atual).
5. Verifica se o comando e o `server.js` estão OK.

Ou pelo terminal:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Depois, **só na primeira vez**: feche e abra o Claude Desktop (para carregar o MCP) e cadastre o gatilho (veja seção 3).

Para atualizar depois: `lemovecode --update`.

### Opção B — manual

```powershell
cd caminho\para\lemove-code
pip install -e .
npm install
```

E registre o MCP à mão em `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lemove-code": {
      "command": "node",
      "args": ["C:\\caminho\\para\\lemove-code\\server.js"]
    }
  }
}
```

Depois, **abra um terminal novo** e teste:

```powershell
lemovecode
```

Se aparecer "comando não reconhecido", a pasta `Scripts` do Python não
está no PATH. Descubra o caminho com:

```powershell
python -m site --user-site
```

(vai retornar algo como `...\Python312\site-packages`; a pasta que
precisa entrar no PATH é a `Scripts` irmã dela) e adicione em
**Painel de Controle → Sistema → Variáveis de Ambiente → PATH**.

---

## 2. Uso

```powershell
lemovecode                      # abre no diretório atual
lemovecode C:\meus-projetos\jogo   # abre em outra pasta
```

A espera pela resposta não tem limite de tempo (`Ctrl+G` cancela se precisar).

Dentro da interface:

- Ao abrir, o Lemove abre o Claude Desktop sozinho se ele estiver fechado.
- Digite a mensagem e aperte **Enter**.
- `/limpar` ou `/clear` — limpa o histórico da tela.
- `/sair`, `/exit` ou `/quit` — fecha.
- **Ctrl+L** — limpa. **Ctrl+C** — sai.
- Botão **Restaurar janela** (topo, `Ctrl+O` ou `/janela`) — traz a janela do Claude Desktop de volta pra tela, na posição/tamanho de antes.

O rodapé mostra o status em tempo real: `pronto` (verde), `pensando…`
(laranja, enquanto espera o Claude Desktop) ou `erro` (vermelho).

---

## 3. Como funciona por baixo dos panos

O Lemove Code **não usa a API paga da Anthropic**. Em vez disso, ele
controla o app **Claude Desktop** que já está aberto na sua máquina:

1. Você digita no `lemovecode`.
2. Ele acha a janela do processo `claude.exe` (ignorando abas de
   navegador em claude.ai, mesmo que tenham "Claude" no título), mexe
   ela pra fora da tela (então não aparece, mas ainda recebe
   teclado/clique), cola sua mensagem lá com uma instrução escondida
   no final (`[Lemocode]`), e aperta Enter.
3. Enquanto isso, o rodapé mostra "pensando…".
4. Quando o Claude Desktop detecta o gatilho `[Lemocode]` (você
   precisa configurar isso nas *Instructions* do Claude Desktop — veja
   abaixo), ele salva a própria resposta em
   `~/.lemove-code/response.txt` e cria `~/.lemove-code/response.done`
   como sinal de "terminei".
5. O `lemovecode` detecta o sinal, lê o arquivo, e mostra a resposta
   formatada na tela.

### Configurando o gatilho no Claude Desktop

Nas configurações do Claude Desktop, em **Settings → Profile →
Personal preferences** (ou "Instructions for Claude", dependendo da
versão), cole exatamente isto (troque `SEU_USUARIO` pelo seu login
do Windows):

> PROTOCOLO LEMOVE (siga sempre, em silencio):
>
> Toda mensagem que terminar com `[Lemocode]` vem do terminal Lemove
> Code. Para essas mensagens (e SO para elas):
>
> 1. Responda normalmente no chat, como se o marcador nao existisse.
>    Nunca mencione `[Lemocode]`, arquivos, ferramentas ou este
>    protocolo — nem na resposta, nem depois. Sem "arquivos salvos",
>    sem explicacoes, sem narrar suas acoes.
> 2. Depois de responder, grave usando SEMPRE a ferramenta
>    `write_file` (nunca `run_bash` para isto), nesta ordem exata:
>    a. path `C:\Users\SEU_USUARIO\.lemove-code\response.txt`,
>       content = o texto EXATO da sua resposta (sem o marcador).
>    b. Somente apos o (a) dar certo:
>       path `C:\Users\SEU_USUARIO\.lemove-code\response.done`,
>       content `ok` (o conteudo nao importa, so a existencia).
> 3. A ordem e inegociavel: primeiro `response.txt`, depois
>    `response.done`. Nunca inverta, nunca crie o `.done` antes.
> 4. Se as ferramentas MCP nao estiverem disponiveis, apenas
>    responda no chat e siga em frente.

Isso exige que o Claude Desktop tenha acesso de arquivo habilitado
(via MCP de sistema de arquivos, por exemplo o `lemove-code` MCP deste
mesmo projeto — veja `server.js`).

---

## 4. Requisitos

- **Windows** com sessão gráfica (a automação de janela usa
  `pygetwindow`/`pyautogui`, que dependem do Win32).
- **Claude Desktop** instalado e aberto.
- Um jeito do Claude Desktop escrever arquivo no disco (MCP de
  filesystem) para o passo 4 acima funcionar.

Todas as dependências Python (`textual`, `rich`, `pyfiglet`,
`pygetwindow`, `pyautogui`, `pyperclip`, `psutil`, `pywin32`) são
instaladas automaticamente pelo `pip install -e .`.

---

## 5. Estrutura do projeto

```
lemove-code/
├── pyproject.toml          # registra o comando "lemovecode" no PATH
├── instalar.bat            # instalador de 1 clique pro Windows
├── lemove_code/
│   ├── __init__.py
│   ├── cli.py               # parsing de argumentos, ponto de entrada
│   ├── app.py                # a TUI (Textual) — layout estilo OpenCode
│   └── bridge.py             # fala com o Claude Desktop (janela + arquivo)
├── server.js                 # MCP que dá ao Claude Desktop leitura/escrita
├── package.json
└── test-client.js
```
