# ADR 0001 — Uma única ação Polkit para todas as operações do helper

## Contexto

A spec (seção 2.1) lista sete operações privilegiadas: `start`, `stop`, `restart`,
`enable`, `disable`, `write-config`, `install-package`. Uma leitura literal sugere
uma ação Polkit por operação.

## Decisão

O arquivo `policy/com.leo.minidlnamanager.policy` declara apenas **uma** ação
(`com.leo.minidlnamanager.manage`), associada via
`org.freedesktop.policykit.exec.path` ao caminho instalado do helper
(`/usr/lib/minidlna-manager/helper`).

## Motivo

`pkexec` autoriza por **caminho do executável**, não por argumento. Ele procura uma
ação cujo `exec.path` bata com o programa invocado e, uma vez autorizado, o processo
inteiro roda como root — os argumentos (`start`, `write-config`, etc.) não passam
pelo Polkit. Declarar uma ação por subcomando criaria a falsa impressão de que cada
uma é checada individualmente, quando na prática só a ação ligada ao `exec.path` do
helper é avaliada.

A restrição fina por subcomando (RNF02: "não aceita comando arbitrário") é
responsabilidade do próprio helper, que só reconhece o conjunto fixo de ações via
`argparse` subparsers — nunca executa um comando vindo da UI sem checar contra essa
whitelist.

## Consequência

Todo usuário autorizado para `com.leo.minidlnamanager.manage` pode executar
qualquer uma das ações da whitelist do helper (não há distinção de nível de
privilégio entre, por exemplo, `restart` e `install-package`). Isso é aceitável para
o escopo do projeto (uso pessoal/desktop), mas fica registrado aqui caso uma
granularidade maior seja necessária no futuro (exigiria trocar `pkexec` por
checagem direta via D-Bus/Polkit Authority dentro do helper).
