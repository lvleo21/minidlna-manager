# Spec Técnica — MiniDLNA Manager

**Versão:** 0.1
**Status:** Draft para aprovação
**Autor:** Leo
**Plataforma alvo:** Linux (distros com systemd + Polkit — Debian/Ubuntu, Fedora, Arch)

---

## 1. Visão Geral

Aplicativo desktop para Linux que gerencia o serviço MiniDLNA de forma gráfica, cobrindo:

1. Ligar/desligar/reiniciar o serviço (`systemctl`).
2. Habilitar/desabilitar o serviço no boot.
3. Editar o arquivo de configuração (`minidlna.conf`) com validação.
4. Exibir status e log básico do serviço.

O app **não** roda como root. Toda operação privilegiada (systemctl, escrita do config em `/etc`, instalação de pacote) passa por **Polkit**, com prompt de autenticação nativo do ambiente gráfico.

Além disso, o app detecta se o MiniDLNA está instalado na máquina e, caso não esteja, oferece instalá-lo diretamente pela interface, sem exigir que o usuário abra um terminal.

---

## 2. Decisões de Arquitetura

### 2.1 Elevação de privilégio — Polkit (caminho aprovado)

- Uma **regra Polkit** (`.policy` XML) declara as ações permitidas: `start`, `stop`, `restart`, `enable`, `disable`, `write-config`.
- Um **helper privilegiado** (script/binário pequeno, não a UI inteira) é o único componente que roda com privilégio elevado, invocado via `pkexec` ou registrado como ação D-Bus.
- A UI **nunca** roda como root. Ela chama o helper, que:
  - Valida a ação solicitada contra uma whitelist fixa (nunca executa comando arbitrário vindo da UI).
  - Executa `systemctl <ação> minidlna.service` OU escreve o novo `minidlna.conf` (após validação).
- Comunicação UI → helper: chamada de processo via `pkexec /usr/lib/minidlna-manager/helper <ação> [args]`, com argumentos tipados e validados nos dois lados (defesa em profundidade).
- A whitelist de ações do helper passa a incluir também `is-installed` (não precisa privilégio, mas fica no mesmo client por conveniência) e `install-package`.

**Por que não sudoers:** funciona, mas exige o usuário editar `/etc/sudoers.d` manualmente ou o instalador fazer isso silenciosamente, o que é mais frágil de auditar e não gera prompt gráfico nativo. Polkit é o padrão que GNOME/KDE já usam para casos idênticos (ex: `gnome-system-monitor` matando processos de outros usuários).

### 2.2 Camada de configuração

- Parser dedicado para `minidlna.conf` (formato `chave=valor`, sem seções, permite múltiplas linhas `media_dir=`).
- Não usar `configparser` puro (exige seção `[section]`) — implementar parser linha-a-linha próprio, preservando comentários e ordem original ao salvar (evitar reescrever o arquivo do zero de forma destrutiva).
- Validação antes de qualquer escrita:
  - Paths de `media_dir` existem e são legíveis.
  - `port` é inteiro válido e não está em uso por outro processo.
  - Enums (`log_level`, tipos de mídia em `media_dir=A,/path`) restritos aos valores aceitos pelo MiniDLNA.
- Escrita sempre via helper privilegiado (arquivo normalmente é `/etc/minidlna.conf`, root:root).
- Após salvar, oferecer `restart` automático (config só é aplicada com reload completo).

### 2.3 Detecção e instalação do MiniDLNA

- **Detecção:** ao abrir o app (e sob demanda), checar se o MiniDLNA está instalado via `shutil.which("minidlnad")` e/ou consulta ao gerenciador de pacotes (`dpkg -s minidlna`, `rpm -q minidlna`, `pacman -Qi minidlna`, conforme a distro detectada). Não depende de privilégio.
- **Instalação:** se ausente, a UI oferece um botão "Instalar MiniDLNA". A ação segue o mesmo modelo do restante do app — helper privilegiado via Polkit, nunca a UI rodando como root.
- **Detecção de gerenciador de pacotes:** o helper identifica o gerenciador disponível na ordem `apt` → `dnf` → `pacman` → `zypper` (verificando existência do binário) e monta o comando de instalação correspondente:
  - `apt-get install -y minidlna`
  - `dnf install -y minidlna`
  - `pacman -S --noconfirm minidlna`
  - `zypper install -y minidlna`
- Se nenhum gerenciador suportado for encontrado, a UI informa isso claramente e sugere instalação manual, sem tentar adivinhar comandos.
- Após instalação bem-sucedida, o app re-executa a detecção de status do serviço (o pacote geralmente já registra a unit systemd, mas não necessariamente a habilita/inicia).
- Build a partir do código-fonte fica fora de escopo — instalação é sempre via pacote da distro (ver seção 7).

### 2.4 Interface

- **GTK4 + libadwaita via PyGObject** — nativo no GNOME (padrão em várias distros), visual consistente, leve, e mantém tudo em Python (alinhado com seu stack atual).
- Alternativa registrada mas não escolhida nesta fase: PyQt6/PySide6 (fica como plano B se libadwaita gerar atrito de packaging).

### 2.5 Empacotamento

- Alvo inicial: **Flatpak** (isola a UI, mas o helper Polkit roda fora do sandbox — padrão já resolvido pelo próprio Flatpak para esse tipo de caso) ou **.deb** simples para uso pessoal.
- Definição fina de empacotamento fica para a Sprint 5 (não bloqueia desenvolvimento das sprints anteriores).

---

## 3. Estrutura de Diretórios (alvo final)

```
minidlna-manager/
├── core/
│   ├── config_parser.py       # leitura/escrita de minidlna.conf (sem privilégio)
│   ├── validator.py           # validação de valores/paths
│   └── service_client.py      # chama o helper via pkexec, parseia retorno
├── helper/
│   └── minidlna_manager_helper.py   # único componente privilegiado
├── ui/
│   ├── app.py
│   ├── windows/
│   └── widgets/
├── policy/
│   └── com.leo.minidlnamanager.policy   # regra Polkit
├── packaging/
│   ├── flatpak/
│   └── deb/
├── tests/
└── docs/
    ├── spec-minidlna-manager.md   # este arquivo
    └── decisions/                 # ADRs por decisão relevante
```

---

## 4. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| RF00a | Detectar se o MiniDLNA está instalado na máquina ao abrir o app |
| RF00b | Oferecer instalação do MiniDLNA pela UI (via helper privilegiado) quando não estiver presente |
| RF00c | Identificar automaticamente o gerenciador de pacotes da distro (apt/dnf/pacman/zypper) e usar o comando correto |
| RF00d | Informar claramente quando nenhum gerenciador suportado for detectado, sem tentar instalar às cegas |
| RF01 | Exibir status atual do serviço (ativo/inativo, habilitado/desabilitado no boot) |
| RF02 | Botão para iniciar o serviço |
| RF03 | Botão para parar o serviço |
| RF04 | Botão para reiniciar o serviço |
| RF05 | Toggle para habilitar/desabilitar no boot |
| RF06 | Visualizar conteúdo atual do `minidlna.conf` de forma estruturada (formulário, não texto cru) |
| RF07 | Editar campos do config com validação antes de salvar |
| RF08 | Adicionar/remover múltiplos `media_dir` |
| RF09 | Salvar config aciona helper privilegiado, com opção de restart automático |
| RF10 | Exibir últimas linhas de log do serviço (via `journalctl -u minidlna`) |
| RF11 | Tratar e exibir erros de permissão/negação do Polkit de forma clara na UI, incluindo falhas de instalação de pacote |

## 5. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | UI nunca roda com privilégio elevado |
| RNF02 | Helper privilegiado não aceita comando arbitrário — apenas ações de uma whitelist fixa |
| RNF03 | Toda escrita de config é validada antes de tocar o arquivo real |
| RNF04 | Falhas de systemctl/D-Bus são capturadas e reportadas sem crash da UI |
| RNF05 | Código documentado (docstrings + comentários em decisões não óbvias) |
| RNF06 | Cobertura de testes automatizados para `core/` (parser, validator) — meta 80%+ |

---

## 6. Fluxo de Trabalho por Sprints

Regra fixa para todo o projeto: **nenhuma sprint começa antes do PR da sprint anterior estar aprovado e mergeado.** Cada sprint termina com um PR único, descrição do que foi entregue, e critérios de aceite verificáveis. Sem aprovação, sem próxima sprint — inclusive se surgir código pronto adiantado, ele fica em branch separada aguardando.

### Sprint 0 — Fundação do projeto
**Objetivo:** esqueleto do repositório, sem lógica de negócio ainda.
- Estrutura de diretórios definida na seção 3.
- `pyproject.toml` / dependências (PyGObject, testes).
- CI básico (lint + testes, mesmo vazios).
- `docs/spec-minidlna-manager.md` (este arquivo) versionado no repo.
- **Critério de aceite:** repo roda `make test` (ou equivalente) sem erro, mesmo sem funcionalidade.
- **PR:** "Sprint 0 — estrutura inicial do projeto"

### Sprint 1 — Camada de configuração (`core/`)
**Objetivo:** parser e validador de `minidlna.conf`, sem UI, sem helper.
- `config_parser.py`: ler arquivo real de exemplo, escrever preservando comentários/ordem.
- `validator.py`: validação de paths, port, enums.
- Testes unitários cobrindo casos normais e malformados.
- **Critério de aceite:** dado um `minidlna.conf` de exemplo, parse → edição em memória → serialização produz arquivo válido e semanticamente equivalente + alterações esperadas.
- **PR:** "Sprint 1 — parser e validação de config"

### Sprint 2 — Helper privilegiado + regra Polkit + instalação
**Objetivo:** componente que efetivamente chama `systemctl`, escreve o config e instala o pacote quando ausente, tudo protegido por Polkit.
- `com.leo.minidlnamanager.policy` com as ações (start/stop/restart/enable/disable/write-config/install-package).
- `helper/minidlna_manager_helper.py`: recebe ação validada, executa, retorna status estruturado (stdout/stderr/exit code).
- Módulo de detecção de gerenciador de pacotes (apt/dnf/pacman/zypper) e execução do comando de instalação correspondente.
- `core/service_client.py`: chama o helper via `pkexec`, trata timeout e negação de permissão; inclui checagem de instalação (`is-installed`, sem privilégio).
- Testes de integração manual documentados (systemctl e instalação real são difíceis de mockar completamente).
- **Critério de aceite:** a partir da linha de comando (sem UI), é possível detectar ausência do MiniDLNA, instalá-lo, e em seguida iniciar/parar/reiniciar o serviço real e escrever um config válido, com prompt de senha do Polkit aparecendo corretamente em cada ação privilegiada.
- **PR:** "Sprint 2 — helper privilegiado, integração Polkit e instalação do pacote"

### Sprint 3 — UI: status, instalação e controle do serviço
**Objetivo:** primeira tela funcional — RF00a a RF00d, RF01 a RF05, RF10.
- Tela principal GTK4/libadwaita: status, botões start/stop/restart, toggle boot, painel de log.
- Fluxo de "não instalado" na abertura do app: card/banner com botão "Instalar MiniDLNA", feedback de progresso e resultado.
- Chamadas assíncronas ao `service_client` (não travar UI durante `pkexec`).
- Tratamento visível de erros/negação de permissão, incluindo falha de instalação (RF11, RNF04).
- **Critério de aceite:** em uma máquina sem MiniDLNA instalado, o usuário consegue instalar, ligar, desligar, reiniciar e ver log do serviço real, do início ao fim, pela UI.
- **PR:** "Sprint 3 — UI de instalação e controle do serviço"

### Sprint 4 — UI: edição de configuração
**Objetivo:** RF06 a RF09.
- Formulário estruturado ligado ao `config_parser` + `validator`.
- Suporte a múltiplos `media_dir` (adicionar/remover linhas).
- Fluxo de salvar → validar → escrever via helper → oferecer restart.
- **Critério de aceite:** usuário edita configs pela UI, valores inválidos são bloqueados com mensagem clara, config salvo reflete corretamente no arquivo real e o MiniDLNA sobe com a nova config após restart.
- **PR:** "Sprint 4 — UI de edição de configuração"

### Sprint 5 — Empacotamento e documentação final
**Objetivo:** entregar algo instalável.
- Empacotamento (Flatpak e/ou .deb, conforme decidido).
- README com instruções de instalação/uso.
- Revisão final de todos os requisitos funcionais/não-funcionais desta spec.
- **Critério de aceite:** instalação limpa em uma VM/distro de teste, app funcional do zero.
- **PR:** "Sprint 5 — empacotamento e documentação"

---

## 7. Fora de Escopo (nesta v0.1)

- Suporte a Windows/macOS.
- Gerenciamento de múltiplas instâncias MiniDLNA simultâneas.
- Transcodificação ou qualquer configuração de mídia além do que o `minidlna.conf` já expõe.
- Interface web/remota (só desktop local).
- Instalação do MiniDLNA por compilação a partir do código-fonte.
- Suporte a distros cujo gerenciador de pacotes não seja apt/dnf/pacman/zypper (nesses casos, apenas orientação manual).

---

## 8. Abertos para decisão futura (não bloqueiam Sprint 0)

- Flatpak vs .deb como formato primário de distribuição.
- Se haverá tema claro/escuro customizado ou apenas herdar do sistema (libadwaita já resolve isso por padrão, então provável resposta é "nenhuma ação extra").
