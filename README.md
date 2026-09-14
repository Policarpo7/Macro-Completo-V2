# Macro Completo V2

Aplicativo desktop Python para Windows com interface em português, perfis por operador/arma e licenças assinadas. Implementação separada do [Macro-Completo original](https://github.com/Policarpo7/Macro-Completo).

## O que foi implementado

- Interface escura com abas **Perfis e ajustes**, **Licença** e **Como testar**.
- Dez modelos iniciais de oito operadores; criação de outros operadores e armas por texto.
- Salvar, duplicar, excluir, importar e exportar perfis em JSON.
- Forças vertical/lateral, intervalo, DPI, sensibilidade e acessórios por perfil.
- Prévia animada sem movimento real do mouse e sem exigir licença.
- F10 ativa/pausa; INSERT pausa imediatamente. Só move ao segurar os dois botões do mouse.
- Alterações de perfil e de licença sempre pausam o motor.
- Acumulação de frações corrige os ajustes laterais pequenos descartados pela V1.
- Licenças Ed25519 por computador, com vencimento verificado durante a execução.

**Os modelos não são presets de recuo calibrados.** Todos começam em vertical 8, lateral 0 e intervalo 9 ms, derivados dos parâmetros da V1. DPI 800 é apenas um campo inicial editável. DPI, sensibilidade e acessórios são anotações do perfil; o programa não altera esses valores no jogo nem calcula compensação automática a partir deles.

| Operador | Modelos de arma |
| --- | --- |
| Ash | R4-C, G36C |
| Sledge | L85A2 |
| Thermite | 556xi |
| Twitch | F2 |
| Jäger | 416-C CARBINE |
| Bandit | MP7 |
| Doc | MP5 |
| Smoke | FMG-9, SMG-11 |

Catálogo inicial não exaustivo. Adicione os demais usando **Novo**. A seleção é manual.

## Distribuição pronta: usuário sem programação

O cliente recebe um ZIP, extrai e abre **MacroCompleto.exe** com dois cliques. Python e dependências já estão incluídos; não existe terminal no uso normal.

**Para você:** abra [Windows executables](https://github.com/Policarpo7/Macro-Completo-V2/actions/workflows/windows-app.yml), escolha a execução verde mais recente e baixe **MacroCompleto-Kit-Proprietario-Windows** em **Artifacts**. O download exige login no GitHub; os artefatos ficam disponíveis por 90 dias e podem ser recriados pelo botão **Run workflow**. Extraia o ZIP e abra **GerenciadorLicencas.exe**.

1. Clique em **Criar emissor** e escolha sua senha (somente na primeira vez).
2. Clique em **Preparar ZIP do cliente**. O gerenciador reúne o aplicativo, a chave pública e instruções simples.
3. Envie ao usuário somente o ZIP gerado.
4. Quando ele enviar o ID, preencha nome, ID e plano, clique em **Gerar key** e **Copiar key**.

O kit do proprietário não é o pacote para enviar ao cliente. A ferramenta administrativa e a chave privada ficam com você. O pacote do cliente tem uma lista fixa de três arquivos: `MacroCompleto.exe`, `public_key.txt` e `LEIA-ME.txt`. O cliente mantém os três na mesma pasta e abre apenas o executável.

A chave pública é lida ao lado do executável; os dados do usuário continuam em LOCALAPPDATA. Preserve o mesmo emissor nas atualizações. Se já criou um emissor pela CLI, selecione a pasta `admin/keys` e coloque nela o `public_key.txt` correspondente.

O workflow testa os fontes, compila ambos os executáveis e abre as duas interfaces compiladas para verificar dependências e inicialização. Essa verificação não valida o comportamento dentro do jogo. Distribuição atual: Windows x64, portátil, sem instalador e sem assinatura de código.

## Executar a partir do código (somente desenvolvimento)

1. Instale [Python](https://www.python.org/downloads/windows/) 3.11 ou superior, incluindo Tcl/Tk e o Python Launcher.
2. No GitHub, clique em **Code → Download ZIP** e extraia tudo.
3. Execute **instalar.bat**. Ele cria o ambiente virtual e instala as dependências.
4. Execute **iniciar.bat**.
5. Na primeira preparação do produto, siga a configuração do emissor abaixo. Sem `public_key.txt`, a interface abre, mas a ativação fica bloqueada.

Alternativa no PowerShell, dentro da pasta:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

A interface abre sem uma key, permitindo editar perfis e usar a prévia. O motor exige uma licença válida.

## Configurar o emissor — somente você, uma vez

Na sua cópia administrativa, execute:

```powershell
.\.venv\Scripts\python.exe -m admin.license_tool init
```

Escolha uma senha com pelo menos 12 caracteres. Serão gerados:

- `admin/keys/issuer-private.pem`: chave privada criptografada, exclusiva do emissor.
- `public_key.txt`: chave pública usada pelo aplicativo para verificar as licenças.

Guarde uma cópia da chave privada e da senha em local seguro. Distribua `public_key.txt` junto do aplicativo. **Não distribua a pasta admin nem a chave privada.** A pasta de chaves, arquivos PEM e arquivos de licença estão no `.gitignore`. Nenhuma chave privada real ou senha está incluída no repositório.

O comando se recusa a sobrescrever chaves existentes. Mantenha o mesmo par ao atualizar o aplicativo para continuar aceitando as licenças já emitidas. Chaves da V1 não são aceitas.

## Emitir uma key

O cliente abre **Licença → Copiar ID do computador** e envia o ID. Na sua máquina, substitua `ID_DO_COMPUTADOR` pelo ID completo de 64 caracteres e informe o cliente:

```powershell
.\.venv\Scripts\python.exe -m admin.license_tool issue --plan diaria --device ID_DO_COMPUTADOR --customer "Nome do cliente"
```

A senha é solicitada de forma interativa. O resultado começa com `MCV2.`; envie a linha inteira ao cliente.

| Opção de --plan | Validade |
| --- | --- |
| diaria | 24 horas |
| semanal | 7 dias |
| mensal | 30 dias corridos |
| lifetime | Sem vencimento |

Para salvar a key em um arquivo novo:

```powershell
.\.venv\Scripts\python.exe -m admin.license_tool issue --plan mensal --device ID_DO_COMPUTADOR --customer "Nome do cliente" --output cliente.lic
```

O prazo começa **na emissão**, em UTC, não na primeira ativação. A tela mostra o vencimento no fuso local do Windows. Renovação é a emissão de outra key; não há cobrança automática nem extensão do saldo anterior. Se você emitir a renovação antes do vencimento, o prazo da nova key já começa naquele momento.

Cada key possui identificador único, plano, cliente, computador e datas cobertos pela assinatura. Ela não é criptografada: esses dados não devem conter informações sensíveis.

## Ativar, vencer e renovar

1. O cliente cola a key em **Licença → Ativar / renovar licença**.
2. O aplicativo verifica assinatura, produto, computador, plano e datas.
3. Uma key inválida não sobrescreve a licença salva anteriormente.
4. Quando a licença vence, o motor pausa e não pode ser reativado.
5. O cliente solicita outra key a você e repete a ativação.
6. Recolar a key antiga, apagar o arquivo de licença ou reinstalar o app **não muda a data assinada de vencimento**.

Lifetime não exige renovação por prazo. Continua vinculada ao mesmo ID de instalação do Windows; reinstalar o Windows pode alterar esse ID e exigir reemissão. O ID é derivado de MachineGuid, não uma identidade física inviolável: instalações clonadas podem compartilhar o identificador.

## Calibrar e testar no seu PC

1. Escolha operador e arma; registre DPI, sensibilidade, mira e acessórios usados.
2. Ajuste vertical e lateral. Lateral negativo: esquerda; positivo: direita.
3. Clique em **Salvar e aplicar**, depois na **Prévia de 1 segundo**.
4. A prévia verifica direção/deslocamento nominal e não simula o recuo da arma.
5. Com uma licença ativa, F10 habilita o motor. Solte e pressione novamente os botões esquerdo e direito.
6. F10 ou INSERT pausa. Fechar a janela encerra o motor e os listeners.
7. Depois da calibração prática, marque **Testei e calibrei este perfil** e salve.
8. Duplique o perfil para outras miras ou acessórios.
9. Reinicie o aplicativo e confirme que os dados foram mantidos.

O movimento é global enquanto ativado; não existe detecção de janela do jogo. Pause antes de trocar de aplicativo. Não há reconhecimento automático de personagem, acesso à memória do jogo ou garantia de compatibilidade com sua configuração.

A V2 usa movimento vertical determinístico para facilitar calibração; a V1 variava aleatoriamente em ±1. Intervalos são nominais: o agendamento do Windows pode alterar o ritmo efetivo.

## Testes automatizados

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O workflow [Tests](https://github.com/Policarpo7/Macro-Completo-V2/actions/workflows/tests.yml) executa no Windows com Python 3.11 e 3.13:

- Assinatura adulterada, emissor incorreto, dados inválidos e computador diferente.
- Os quatro planos, vencimento exato, reativação sem renovação e nova key.
- Vencimento durante a sessão e detecção básica de relógio atrasado.
- Persistência, importação, valores inválidos e duplicação de perfis.
- Acumulação lateral positiva/negativa e pausa do motor.
- Teste da interface salvando perfil, ativando/renovando e abrindo prévia.

O teste da interface substitui o início dos listeners e usa chaves efêmeras em uma pasta temporária. Ele não move o mouse, não usa licenças reais e não testa a integração com Rainbow Six. A validação prática no Windows do usuário permanece necessária.

## Dados locais e limites do licenciamento

Dados do usuário: `%LOCALAPPDATA%\PolicarpoMacroV2`.

- `profiles.json`: perfis salvos; exporte pela interface para fazer backup.
- `license.json`: token assinado.
- `clock.json`: último horário observado, usado para detectar retrocessos superiores a cinco minutos.

As gravações usam substituição atômica. Arquivos corrompidos são reportados, sem sobrescrever silenciosamente os perfis. Se houver corrupção, preserve o arquivo para recuperação e restaure um backup antes de reiniciar.

Este licenciamento é **offline**: o relógio e os arquivos locais não são fontes de tempo invioláveis. A sessão também usa prazo monotônico para evitar que pequenos atrasos do relógio prolonguem uma execução aberta. Não há revogação remota nem validação online. Como o cliente controla o código e o computador, ele pode modificar a validação ou substituir a chave pública. Para distribuição comercial com controle mais forte, o próximo passo é um serviço de ativação/renovação com tempo do servidor e revogação.

## Referências

- [Documentação Ed25519 da cryptography](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
- Catálogo oficial: [Ash](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/ash), [Sledge](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/sledge), [Thermite](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/thermite), [Twitch](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/twitch), [Jäger](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/jager), [Bandit](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/bandit), [Doc](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/doc), [Smoke](https://www.ubisoft.com/en-us/game/rainbow-six/siege/game-info/operators/smoke). Estas páginas sustentam nomes/armas, não valores de compensação.

Empacotamento: [PyInstaller — executáveis](https://pyinstaller.org/en/stable/usage.html) e [caminhos em execução](https://pyinstaller.org/en/stable/runtime-information.html).
