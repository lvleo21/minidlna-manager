# Testes manuais — Sprint 4

A validação e o formulário foram verificados visualmente sem tocar em
`/etc/minidlna.conf` real (campos carregam corretamente, valores inválidos são
bloqueados com mensagem clara). O que falta é o fluxo real de escrita +
restart, que muda o sistema de verdade — rode numa máquina/VM de teste com o
helper e a regra Polkit já instalados (ver `docs/testing/sprint2-manual-testing.md`).

## 1. Abrir a configuração pela UI

```bash
python -m ui.app
```

Com o MiniDLNA instalado, clique no ícone de engrenagem no cabeçalho. Esperado:
janela "Configuração do MiniDLNA" com os campos carregados a partir do
`/etc/minidlna.conf` real (porta, nível de log, diretórios de mídia).

## 2. Editar e salvar

- Altere a porta para um valor válido, adicione um novo diretório de mídia
  (com um path real e legível) e remova um existente.
- Clique em "Salvar". Esperado: prompt do Polkit; após autenticar, toast
  "Config salvo." com um botão "Reiniciar agora".
- Confirme com `sudo cat /etc/minidlna.conf` que o arquivo reflete exatamente
  as mudanças feitas (e que comentários/demais chaves não mudaram).

## 3. Reiniciar a partir do toast

Clique em "Reiniciar agora" no toast. Esperado: prompt do Polkit, toast
"MiniDLNA reiniciado.", e `systemctl status minidlna.service` mostra o serviço
ativo servindo a nova config (novo diretório de mídia sendo escaneado).

## 4. Validação bloqueando o save

Digite um valor de porta inválido ou um path de diretório inexistente e clique
em "Salvar". Esperado: os campos problemáticos ficam com borda vermelha, um
toast lista os erros, e nenhum prompt do Polkit aparece (o helper não é
chamado quando a validação falha).
