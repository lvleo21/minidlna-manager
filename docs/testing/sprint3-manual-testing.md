# Testes manuais — Sprint 3

O fluxo completo (instalar → ligar/desligar/reiniciar → ver log, tudo pela UI, com
prompts reais do Polkit) não é seguro de automatizar — ele instala um pacote e
altera um serviço systemd de verdade. Rode isto numa máquina/VM de teste.

## 1. Instalar a regra Polkit e o helper no destino final

```bash
sudo install -Dm755 helper/minidlna_manager_helper.py /usr/lib/minidlna-manager/helper
sudo install -Dm644 policy/com.leo.minidlnamanager.policy \
  /usr/share/polkit-1/actions/com.leo.minidlnamanager.policy
```

## 2. Abrir a UI numa máquina sem MiniDLNA instalado

```bash
python -m ui.app
```

Esperado: banner "MiniDLNA não está instalado" visível, botões
Iniciar/Parar/Reiniciar e o toggle "Iniciar no boot" desabilitados, status
"Desconhecido", log vazio.

## 3. Instalar pela UI

Clique em "Instalar MiniDLNA". Esperado: botão muda para "Instalando…" e fica
desabilitado; prompt gráfico do Polkit aparece; após autenticar, toast de sucesso,
banner desaparece, controles ficam habilitados e o status passa a mostrar
"Inativo".

## 4. Controlar o serviço pela UI

- Clique em "Iniciar" → prompt do Polkit → toast de sucesso → status muda para
  "Ativo".
- Clique em "Atualizar log" → linhas recentes do `journalctl -u minidlna.service`
  aparecem no painel.
- Clique em "Reiniciar" e depois "Parar", confirmando o status e o toast a cada
  ação.
- Alterne "Iniciar no boot" → prompt do Polkit → toast de sucesso; confirme com
  `systemctl is-enabled minidlna.service` no terminal.

## 5. Negação de permissão

Repita uma ação privilegiada e cancele o prompt do Polkit. Esperado: toast de
erro claro (RF11), a UI não trava nem fecha (RNF04), e o toggle de boot volta
para o estado anterior caso a ação cancelada tenha sido nele.
