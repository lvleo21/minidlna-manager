# MiniDLNA Manager

Aplicativo desktop (GTK4 + libadwaita) para gerenciar o serviço MiniDLNA no
Linux. A UI nunca roda com privilégio elevado — toda operação que precisa de
root (systemctl, escrita em `/etc/minidlna.conf`, instalação do pacote) passa
por um helper dedicado, autorizado via Polkit.

## Funcionalidades

- Detecta se o MiniDLNA está instalado e oferece instalar direto pela
  interface (apt/dnf/pacman/zypper, com detecção automática do gerenciador)
- Iniciar, parar, reiniciar o serviço e alternar o início automático no boot
- Ver as últimas linhas de log do serviço
- Editar `minidlna.conf` por um formulário estruturado — nome do servidor,
  porta, interface de rede, nível de log (por categoria) e diretórios de
  mídia (com seletor nativo de pasta) — com validação antes de qualquer
  escrita e opção de reiniciar o serviço logo após salvar
- Aba de dispositivos conectados, lida direto da própria página de status do
  `minidlnad`

## Instalação

### Arch / Manjaro

```bash
cd packaging/arch
makepkg -si
```

Instala o app, o helper privilegiado (`/usr/lib/minidlna-manager/helper`) e a
regra Polkit (`/usr/share/polkit-1/actions/`). O MiniDLNA em si não é uma
dependência obrigatória do pacote — se estiver ausente, o próprio app oferece
instalá-lo na primeira execução.

Depois de instalado, abra pelo menu de aplicativos ou rode `minidlna-manager`.

### Outras distros

Ainda não há pacote `.deb` nem Flatpak prontos — ver `packaging/deb/README.md`
e `packaging/flatpak/README.md`. Enquanto isso, dá para rodar direto do
código-fonte (ver "Desenvolvimento" abaixo) desde que o helper e a regra
Polkit sejam instalados manualmente:

```bash
sudo install -Dm755 helper/minidlna_manager_helper.py /usr/lib/minidlna-manager/helper
sudo install -Dm644 policy/com.leo.minidlnamanager.policy \
  /usr/share/polkit-1/actions/com.leo.minidlnamanager.policy
```

## Desenvolvimento

```bash
make install   # instala dependências (modo editável + dev)
make test      # roda a suíte de testes
make lint      # roda o linter (ruff)
python -m ui.app   # roda o app a partir do código-fonte
```

Requer PyGObject com GTK4 e libadwaita instalados no sistema (não é possível
instalar via pip puro — normalmente vêm do gerenciador de pacotes da distro,
ex.: `python-gobject`, `gtk4`, `libadwaita` no Arch).
