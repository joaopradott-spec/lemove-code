# Lemove Code

Terminal bonito, estilo **OpenCode** / **Claude Code**, que usa o **Claude
Desktop de graça** como cérebro — sem precisar de API paga.

Depois de instalado, digitar `lemovecode` em qualquer `cmd.exe` ou
PowerShell abre a interface, de qualquer pasta — exatamente como o
comando `opencode` funciona no projeto original.

---

## 1. Instalação

Precisa de **Python 3.9+** instalado no Windows (marque "Add python.exe
to PATH" no instalador do Python, se ainda não tiver).

### Opção A — instalador automático

Dê duplo clique em **`instalar.bat`** (ou rode pelo terminal). Ele:

1. Confere se o Python está no PATH.
2. Roda `pip install -e .` na pasta do projeto.
3. Isso cria o comando `lemovecode` — o `pip` gera um `lemovecode.exe`
   de lançador dentro da pasta `Scripts` do Python, que normalmente já
   está no PATH do Windows.

### Opção B — manual

```powershell
cd caminho\para\lemove-code
pip install -e .
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
lemovecode --timeout 180        # espera até 3 min pela resposta
```

Dentro da interface:

- Digite a mensagem e aperte **Enter**.
- `/limpar` ou `/clear` — limpa o histórico da tela.
- `/sair`, `/exit` ou `/quit` — fecha.
- **Ctrl+L** — limpa. **Ctrl+C** — sai.

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
versão), adicione algo como:

> Sempre que a mensagem terminar com `[Lemocode]`, além de responder
> normalmente no chat, salve a resposta completa em texto puro no
> arquivo `~/.lemove-code/response.txt` (crie a pasta se não existir)
> e, em seguida, crie/atualize um arquivo vazio em
> `~/.lemove-code/response.done` para sinalizar que terminou de
> escrever.

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
