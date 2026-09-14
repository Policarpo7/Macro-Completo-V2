import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from macro.licensing import encode, decode

INSTRUCTIONS = """MACRO COMPLETO V2

1. Extraia TODOS os arquivos deste ZIP para uma pasta.
2. Abra MacroCompleto.exe com dois cliques.
3. Na aba Licenca, clique em Copiar ID e envie ao fornecedor.
4. Cole a key recebida e clique em Ativar / renovar licenca.
5. Escolha seu perfil e use F10 para ativar/pausar. INSERT pausa.

Nao precisa instalar Python. Nao precisa abrir comandos.
Mantenha public_key.txt na mesma pasta do aplicativo.
"""


def provision(folder, password):
    folder = Path(folder)
    private_path, public_path = folder / "issuer-private.pem", folder / "public_key.txt"
    if private_path.exists() or public_path.exists():
        raise ValueError("Este local já possui um emissor. Use-o para gerar as keys.")
    if len(password) < 12:
        raise ValueError("Escolha uma senha com pelo menos 12 caracteres.")
    folder.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.BestAvailableEncryption(password.encode()))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with private_path.open("xb") as handle:
        handle.write(private)
    try:
        with public_path.open("x", encoding="ascii") as handle:
            handle.write(encode(public) + "\n")
    except Exception:
        private_path.unlink()
        raise


def load_issuer(folder, password):
    key = serialization.load_pem_private_key(
        (Path(folder) / "issuer-private.pem").read_bytes(), password=password.encode())
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Emissor incompatível.")
    return key


def package_client(executable, folder, output):
    executable, folder, output = Path(executable), Path(folder), Path(output)
    if executable.suffix.lower() != ".exe" or executable.name != "MacroCompleto.exe":
        raise ValueError("Selecione o arquivo MacroCompleto.exe do kit.")
    public = (folder / "public_key.txt").read_text(encoding="ascii").strip()
    if len(decode(public)) != 32:
        raise ValueError("Chave pública inválida.")
    # Allowlist: never include the private key or the administrator application.
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(executable, "MacroCompleto.exe")
            archive.writestr("public_key.txt", public + "\n")
            archive.writestr("LEIA-ME.txt", INSTRUCTIONS)
    except FileExistsError:
        raise ValueError("O ZIP já existe. Escolha outro nome.")
    except Exception:
        if output.exists():
            output.unlink()
        raise
