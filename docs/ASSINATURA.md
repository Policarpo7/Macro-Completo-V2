# Assinatura do aplicativo para Windows

## Situação atual

A integração foi preparada, mas nenhum certificado de assinatura de código do proprietário foi fornecido e nenhum executável foi assinado por esta configuração ainda. Os downloads anteriores continuam sem assinatura.

O licenciamento MCV2 (diário, semanal, mensal e vitalício) é independente da assinatura Authenticode do programa.

## O que depende de você

1. Solicite um certificado **Code Signing RSA com eSigner** ao [SSL.com](https://www.ssl.com/products/software-integrity/code-signing/). Confirme com o fornecedor a elegibilidade de pessoa física ou jurídica brasileira, documentos, preço total do certificado e assinatura em nuvem antes de contratar. Não compre um certificado de site HTTPS.
2. Complete a validação de identidade diretamente com o fornecedor. Não envie documentos, senha, chave privada ou segredo de autenticação nesta conversa.
3. Depois da emissão, habilite a integração eSigner conforme a [documentação oficial](https://github.com/SSLcom/esigner-codesign). A assinatura automatizada exige usuário, senha, credential ID e segredo TOTP autorizado para esse uso.
4. No repositório, abra **Settings → Environments → New environment**, com nome **code-signing**. Se já existir, abra-o.
5. Em **Environment secrets**, cadastre ES_USERNAME, ES_PASSWORD, CREDENTIAL_ID e ES_TOTP_SECRET. Use exclusivamente os dados reais do seu emissor eSigner.
6. Em **Environment variables**, cadastre SIGNING_CERT_SHA1: impressão digital SHA1 do certificado público emitido, sem espaços. SHA1 aqui identifica o certificado, não escolhe o algoritmo de assinatura do arquivo.
7. Em **Actions → Windows executables → Run workflow**, escolha **main** e mantenha **assinar** marcado. A execução chama o serviço e pode consumir sua franquia de assinaturas.
8. Baixe **MacroCompleto-Kit-ASSINADO-Windows** somente quando toda a execução estiver verde.

A contratação e os valores não foram aprovados ou pagos automaticamente. A integração fica inativa nos pushes normais; só solicita assinatura na execução manual marcada. Não é necessário trocar o emissor das keys MCV2 existentes.

## Como o fluxo verifica a entrega

- Compila e testa os dois programas.
- Usa a ação oficial SSL.com fixada em um commit, em produção, com verificação de malware habilitada.
- Exige assinatura Authenticode válida no Windows, certificado esperado, finalidade de assinatura de código, RSA e carimbo de tempo.
- Reabre os executáveis após a assinatura.
- Só disponibiliza o artefato ASSINADO se todas as verificações passarem.
- Se faltar configuração, falha antes de solicitar assinatura. Se a assinatura falhar, não entrega o pacote como assinado.
- Builds automáticos continuam disponíveis com nome **TESTE-SEM-ASSINATURA**, identificados também em STATUS-ASSINATURA.txt.

Use credenciais com o menor acesso possível. Configure acesso ao environment apenas para main e proteja alterações nos workflows conforme os recursos do seu plano GitHub. Uma execução de assinatura usa credenciais do serviço contratado e não deve rodar código de contribuidores não confiáveis.

## Limites

Assinatura não é uma garantia de ausência de malware ou de liberação por todos os controles do Windows. SmartScreen, políticas empresariais, Defender e componentes internos extraídos pelo empacotador ainda podem exigir análise. É necessário testar o pacote final no computador que apresentou o bloqueio. Não há alteração ou desativação do Defender neste projeto.

Certificado autoassinado não substitui certificado público reconhecido. A disponibilidade pública do Microsoft Artifact Signing consultada não inclui pessoa física residente no Brasil; por isso esta integração não exige criar uma conta Azure incompatível com esse requisito.

## Fontes

- [Microsoft: Controle Inteligente de Aplicativos](https://support.microsoft.com/pt-br/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions).
- [Microsoft: disponibilidade do Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart).
- [SSL.com: ação oficial eSigner](https://github.com/SSLcom/esigner-codesign).
