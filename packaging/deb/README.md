# Empacotamento `.deb`

Gera um pacote binário `minidlna-manager_<versão>_all.deb` para Debian/Ubuntu
e derivados.

## Build

```bash
./build-deb.sh              # saída em packaging/deb/dist/
./build-deb.sh /outro/dir   # ou um diretório de saída à escolha
```

O script monta o pacote direto da árvore de trabalho usando só `dpkg-deb` —
sem `debhelper`, sem `dpkg-buildpackage` — justamente para que também rode na
máquina de desenvolvimento do projeto, que é Arch-based. O único requisito é
ter `dpkg-deb` instalado (no Arch: `pacman -S dpkg`).

A versão sai de `changelog`, e o script aborta se ela divergir da versão em
`pyproject.toml` — ao subir a versão, atualize os dois.

## O que o pacote instala

| Caminho | Conteúdo |
| --- | --- |
| `/usr/bin/minidlna-manager` | launcher (`launcher`) |
| `/usr/share/minidlna-manager/{core,ui}/` | código Python do app |
| `/usr/lib/minidlna-manager/helper` | helper privilegiado |
| `/usr/share/polkit-1/actions/` | ação Polkit |
| `/usr/share/applications/` | entrada `.desktop` |
| `/usr/share/man/man1/` | página de manual |

Diferente do pacote Arch, `core` e `ui` **não** vão para
`/usr/lib/python3/dist-packages`: são nomes genéricos demais para ocupar o
namespace compartilhado do sistema. Ficam num diretório privado, e
`/usr/bin/minidlna-manager` o insere no `sys.path`. Como isso deixa o código
fora do alcance do byte-compile automático do `dh_python3`, o `postinst` chama
`py3compile` e o `prerm` chama `py3clean` — sem `__pycache__` órfão na remoção.

## Dependências

`python3 (>= 3.10)`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`,
`pkexec | policykit-1` (o pacote do `pkexec` foi separado do `policykit-1` no
Debian 12), `acl` e `systemd`. O `minidlna` é apenas `Recommends`: se faltar, o
próprio app oferece instalá-lo.

## Validação

O pacote é montado com compressão `xz` (não `zstd`): o `dpkg` do Debian/Ubuntu
rejeita um `control.tar.zst`, e o `dpkg-deb` do Arch usa `zstd` por padrão.

`test-deb.sh` instala o pacote, verifica o que ele entrega (imports do app,
byte-compile do `postinst`, helper recusando subcomando fora da whitelist, ação
Polkit apontando para o helper instalado, entrada `.desktop` e man page) e por
fim faz `purge` conferindo que nada sobra. Como ele instala e remove pacotes,
rode num contêiner — não na máquina de trabalho:

```bash
docker run --rm -v "$PWD:/src:ro" -w /tmp debian:bookworm \
  bash -c 'cp -r /src /work && cd /work && ./test-deb.sh dist/*.deb'
```

Validado assim em `debian:bookworm` e `ubuntu:22.04`.

## CI

- `.github/workflows/ci.yml` (job `deb-package`): a cada push/PR builda o
  pacote, roda `lintian --fail-on error,warning` e o `test-deb.sh`, e sobe o
  `.deb` como artefato do workflow. `initial-upload-closes-no-bugs` é
  suprimido — só se aplica a uploads para o arquivo do Debian.
- `.github/workflows/release.yml`: numa tag `v*`, confere que a tag bate com a
  versão do `pyproject.toml`, repete build/lint/teste e anexa o `.deb` à
  release correspondente.
