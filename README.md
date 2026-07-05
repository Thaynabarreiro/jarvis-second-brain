# Jarvis — Segundo Cérebro com Voz 🎩

Galáxia 3D das suas notas em markdown + assistente de voz (mordomo britânico) que responde
a partir delas, voa a câmera até a nota-fonte e cria notas novas por voz ("lembre que…").

Só precisa de **Python 3** e **Google Chrome**. Sem npm, sem instalação de pacotes.

## Como funciona

| Arquivo | Papel |
|---|---|
| `build.py` | escaneia suas notas `.md` e gera `viewer/graph-data.js` (a galáxia) |
| `server.py` | servidor local (porta 4700) com os endpoints `/chat` e `/remember` |
| `viewer/index.html` | a interface: galáxia 3D, chat, microfone e voz |
| `config.json` | sua API key, modelo e caminho da pasta de notas (fica só na sua máquina) |

A API key nunca vai para o navegador — só o servidor a lê. Sem API key, o `/chat`
usa `claude -p` (assinatura do Claude Code) como fallback.

---

## 🪟 Instalação no Windows (passo a passo)

### 1. Instale o Python 3
- Baixe em <https://www.python.org/downloads/windows/>
- **IMPORTANTE:** na primeira tela do instalador, marque a caixa **"Add python.exe to PATH"**.

### 2. Baixe este projeto
- Neste repositório no GitHub: botão verde **Code → Download ZIP**
- Extraia o ZIP para uma pasta fácil, ex.: `C:\jarvis`

### 3. Configure
- Na pasta, copie `config.example.json` e renomeie a cópia para `config.json`
- Abra o `config.json` no Bloco de Notas e edite:

```json
{
  "api_key": "SUA-CHAVE-AQUI",
  "model": "claude-opus-4-8",
  "notes_dir": "C:\\Users\\SEU_USUARIO\\Documents\\MinhasNotas"
}
```

- `api_key`: crie em <https://console.anthropic.com> (US$ 5 de crédito duram muito).
  Digite a chave você mesmo no arquivo — nunca cole a chave em chats.
- `notes_dir`: caminho da pasta com suas notas `.md` (vault do Obsidian, por exemplo).
  No Windows use barra dupla `\\` como no exemplo. Se deixar `""`, ele usa a pasta `notes/` do projeto —
  crie alguns arquivos `.md` dentro dela para começar.

### 4. Rode
Abra o **Prompt de Comando** (tecla Windows → digite `cmd`) e execute:

```bat
cd C:\jarvis
python build.py
python server.py
```

### 5. Abra no Chrome
Acesse <http://localhost:4700> **no Google Chrome** (o microfone e a voz precisam dele).

- Clique uma vez na página → ele dá as boas-vindas em voz alta
- Clique no 🎙, fale sua pergunta em português → ele responde falando e voa até a nota
- Diga ou digite **"lembre que [qualquer coisa]"** → nasce uma nota nova na galáxia

### Atualizar a galáxia depois de editar notas
Rode `python build.py` de novo e recarregue a página (Ctrl+Shift+R).

---

## Problemas comuns

| Sintoma | Solução |
|---|---|
| Mic não funciona | Chrome → cadeado na barra de endereço → permitir Microfone |
| Sem som | Clique na página uma vez antes (navegador bloqueia áudio sem interação) |
| Página desatualizada | Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac) |
| Resposta genérica | Confira o `notes_dir` no `config.json` e rode `python build.py` de novo |
| `python` não reconhecido | Reinstale o Python marcando "Add to PATH" |

---

Baseado no prompt pack "Build Your Own Jarvis" (Zubair Trabzada · AI Workshop),
construído com Claude Code.
