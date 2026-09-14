import argparse
import getpass
import re
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from macro.licensing import PRODUCT, PLAN_DAYS, canonical, encode

ROOT = Path(__file__).resolve().parents[1]


def issue(private_key, plan, device, customer, now=None):
    if plan not in PLAN_DAYS:
        raise ValueError("Plano inválido.")
    if not re.fullmatch(r"[a-f0-9]{64}", device):
        raise ValueError("O ID do computador deve ter 64 caracteres hexadecimais.")
    if not customer.strip() or len(customer) > 200:
        raise ValueError("Informe o nome do cliente (até 200 caracteres).")
    issued = int(time.time() if now is None else now)
    days = PLAN_DAYS[plan]
    payload = {"v": 1, "product": PRODUCT, "id": str(uuid.uuid4()),
               "device": device, "customer": customer.strip(), "plan": plan,
               "issued_at": issued,
               "expires_at": None if days is None else issued + days * 86400}
    body = canonical(payload)
    return "MCV2." + encode(body) + "." + encode(private_key.sign(body))


def main():
    parser = argparse.ArgumentParser(description="Emissor de licenças Macro Completo V2")
    sub = parser.add_subparsers(dest="command", required=True)
    initialize = sub.add_parser("init", help="Criar par de chaves uma única vez")
    initialize.add_argument("--private", type=Path, default=ROOT / "admin/keys/issuer-private.pem")
    initialize.add_argument("--public", type=Path, default=ROOT / "public_key.txt")
    emit = sub.add_parser("issue", help="Emitir uma key vinculada ao computador")
    emit.add_argument("--private", type=Path, default=ROOT / "admin/keys/issuer-private.pem")
    emit.add_argument("--plan", choices=list(PLAN_DAYS), required=True)
    emit.add_argument("--device", required=True)
    emit.add_argument("--customer", required=True)
    emit.add_argument("--output", type=Path, help="Arquivo .lic novo (opcional)")
    args = parser.parse_args()
    try:
        if args.command == "init":
            if args.private.exists() or args.public.exists():
                raise ValueError("Já existe uma chave. Não substitua o emissor de licenças existentes.")
            password = getpass.getpass("Senha para proteger a chave privada (mínimo 12 caracteres): ")
            if len(password) < 12 or password != getpass.getpass("Repita a senha: "):
                raise ValueError("Senha curta ou confirmação diferente.")
            key = Ed25519PrivateKey.generate()
            encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.BestAvailableEncryption(password.encode()))
            public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            args.private.parent.mkdir(parents=True, exist_ok=True)
            args.public.parent.mkdir(parents=True, exist_ok=True)
            with args.private.open("xb") as output:
                output.write(encrypted)
            try:
                with args.public.open("x", encoding="ascii") as output:
                    output.write(encode(public) + "\n")
            except Exception:
                args.private.unlink()
                raise
            print("Emissor criado. Faça backup da chave privada e da senha.")
            print("Distribua apenas public_key.txt com o aplicativo.")
        else:
            password = getpass.getpass("Senha da chave privada: ")
            key = serialization.load_pem_private_key(args.private.read_bytes(), password=password.encode())
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("Tipo de chave incorreto.")
            token = issue(key, args.plan, args.device, args.customer)
            if args.output:
                with args.output.open("x", encoding="ascii") as output:
                    output.write(token + "\n")
                print("Key salva em", args.output)
            else:
                print(token)
            print("Validade a partir da emissão; mensal = 30 dias. Reutilizar a key não renova o prazo.")
    except (OSError, ValueError) as error:
        parser.exit(1, "Erro: " + str(error) + "\n")


if __name__ == "__main__":
    main()
