# Testes manuais — Sprint 2

`systemctl` real e instalação de pacote não são mockáveis com segurança em CI.
Este roteiro cobre o critério de aceite da Sprint 2 numa máquina de teste
(idealmente uma VM), sem UI.

## 1. Instalar a regra Polkit e o helper no destino final

```bash
sudo install -Dm755 helper/minidlna_manager_helper.py /usr/lib/minidlna-manager/helper
sudo install -Dm644 policy/com.leo.minidlnamanager.policy \
  /usr/share/polkit-1/actions/com.leo.minidlnamanager.policy
```

## 2. Detectar ausência do MiniDLNA (sem privilégio)

```bash
python -m core.service_client is-installed
```

Esperado: `"installed": false` numa máquina limpa, com `"package_manager"`
indicando o gerenciador detectado (apt/dnf/pacman/zypper).

## 3. Instalar o pacote (aciona prompt do Polkit)

```bash
python -m core.service_client install-package
```

Esperado: prompt gráfico de autenticação do Polkit aparece; após autenticar,
`"ok": true` e o pacote é instalado. Repita o passo 2 e confirme
`"installed": true`.

## 4. Controlar o serviço (cada ação aciona o prompt do Polkit)

```bash
python -m core.service_client start
python -m core.service_client restart
python -m core.service_client stop
python -m core.service_client enable
python -m core.service_client disable
```

Confirme com `systemctl status minidlna.service` que cada ação teve o efeito
esperado no sistema real.

## 5. Escrever um config válido (aciona o prompt do Polkit)

```bash
python -c "
from core import service_client
print(service_client.write_config(open('tests/fixtures/minidlna.conf.sample').read()))
"
sudo cat /etc/minidlna.conf   # confirma o conteúdo escrito
```

## 6. Negação de permissão

Repita qualquer ação privilegiada e cancele o prompt do Polkit (ou erre a
senha até esgotar as tentativas). Esperado: `service_client` levanta
`PermissionDeniedError` em vez de travar ou lançar um traceback não tratado.
