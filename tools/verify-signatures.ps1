param(
    [Parameter(Mandatory=$true)][string]$Directory,
    [Parameter(Mandatory=$true)][string]$ExpectedThumbprint
)
$ErrorActionPreference = "Stop"
$expected = ($ExpectedThumbprint -replace '\s', '').ToUpperInvariant()
if ($expected -notmatch '^[0-9A-F]{40}$') {
    throw "Configure a impressao digital SHA1 do certificado aprovado (40 caracteres)."
}
foreach ($name in @("MacroCompleto.exe", "GerenciadorLicencas.exe")) {
    $path = Join-Path $Directory $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Executavel ausente: $name"
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    if ($signature.Status -ne "Valid" -or $null -eq $signature.SignerCertificate) {
        throw "Assinatura nao confiavel: $name ($($signature.Status))."
    }
    if ($signature.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $expected) {
        throw "O certificado de $name nao corresponde ao editor configurado."
    }
    if ($null -eq $signature.TimeStamperCertificate) {
        throw "Carimbo de tempo ausente: $name"
    }
    $eku = $signature.SignerCertificate.EnhancedKeyUsageList |
        Where-Object { $_.ObjectId.Value -eq "1.3.6.1.5.5.7.3.3" -or $_.ObjectId -eq "1.3.6.1.5.5.7.3.3" }
    if (-not $eku) { throw "Certificado sem finalidade de assinatura de codigo: $name" }
    if ($signature.SignerCertificate.PublicKey.Oid.Value -ne "1.2.840.113549.1.1.1") {
        throw "Use certificado RSA para compatibilidade com Smart App Control."
    }
    Write-Host "$name : assinatura do editor e carimbo de tempo verificados."
}
