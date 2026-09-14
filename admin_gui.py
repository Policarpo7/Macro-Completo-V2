import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from admin.distribution import provision, load_issuer, package_client
from admin.license_tool import issue
from macro.licensing import PLAN_LABELS

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


class Admin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Policarpo • Gerenciador de licenças (somente proprietário)")
        self.geometry("820x650")
        self.minsize(760, 620)
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="GERENCIADOR DE LICENÇAS", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Guarde este aplicativo e sua pasta do emissor. Envie ao cliente apenas o ZIP gerado.").pack(anchor="w", pady=10)
        self.folder = tk.StringVar(value=str(Path.home() / "Documents" / "PolicarpoLicencas"))
        ttk.Label(frame, text="Pasta do emissor (chave privada e pública):").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.folder).pack(fill="x", pady=4)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=6)
        ttk.Button(row, text="Escolher pasta", command=self.choose_folder).pack(side="left")
        ttk.Button(row, text="1. Criar emissor (uma vez)", command=self.create).pack(side="left", padx=8)
        ttk.Button(row, text="2. Preparar ZIP do cliente", command=self.package).pack(side="left")
        ttk.Separator(frame).pack(fill="x", pady=14)
        ttk.Label(frame, text="3. Emitir ou renovar uma key", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.customer, self.device, self.plan = tk.StringVar(), tk.StringVar(), tk.StringVar(value="Mensal")
        for text, variable in (("Nome do cliente", self.customer), ("ID copiado do aplicativo do cliente", self.device)):
            ttk.Label(frame, text=text).pack(anchor="w", pady=(8, 2))
            ttk.Entry(frame, textvariable=variable).pack(fill="x")
        ttk.Label(frame, text="Plano").pack(anchor="w", pady=(8, 2))
        ttk.Combobox(frame, textvariable=self.plan, values=list(PLAN_LABELS.values()), state="readonly").pack(anchor="w")
        ttk.Label(frame, text="Diária: 24h / Semanal: 7 dias / Mensal: 30 dias / Vitalícia: sem vencimento.\n"
                              "O prazo começa agora, na emissão.").pack(anchor="w", pady=6)
        ttk.Button(frame, text="Gerar key", command=self.generate).pack(anchor="w", pady=6)
        self.output = tk.Text(frame, height=5, wrap="char")
        self.output.pack(fill="both", expand=True)
        ttk.Button(frame, text="Copiar key", command=self.copy).pack(anchor="w", pady=8)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder.set(folder)

    def create(self):
        password = simpledialog.askstring("Criar emissor", "Escolha uma senha com pelo menos 12 caracteres:", show="*")
        if password is None:
            return
        confirmation = simpledialog.askstring("Confirmar senha", "Repita a senha:", show="*")
        if confirmation != password:
            messagebox.showerror("Senha", "As senhas não coincidem.")
            return
        try:
            provision(self.folder.get(), password)
            messagebox.showinfo("Emissor criado", "Faça backup da pasta do emissor e guarde a senha.\n"
                                "Use o mesmo emissor para todas as novas versões.")
        except Exception as error:
            messagebox.showerror("Criar emissor", str(error))

    def package(self):
        executable = ROOT / "MacroCompleto.exe"
        if not executable.exists():
            selected = filedialog.askopenfilename(title="Selecione MacroCompleto.exe", filetypes=[("Aplicativo", "*.exe")])
            if not selected:
                return
            executable = Path(selected)
        output = filedialog.asksaveasfilename(title="Salvar novo pacote do cliente", initialfile="MacroCompleto-Cliente.zip",
                                            defaultextension=".zip", filetypes=[("ZIP", "*.zip")])
        if not output:
            return
        try:
            package_client(executable, self.folder.get(), output)
            messagebox.showinfo("Pronto para enviar", "Envie este ZIP ao cliente. Ele só precisa extrair, abrir MacroCompleto.exe e colar a key.")
        except Exception as error:
            messagebox.showerror("Preparar pacote", str(error))

    def generate(self):
        password = simpledialog.askstring("Emissor", "Senha da chave privada:", show="*")
        if password is None:
            return
        try:
            private = load_issuer(self.folder.get(), password)
            plan = next(key for key, label in PLAN_LABELS.items() if label == self.plan.get())
            token = issue(private, plan, self.device.get().strip(), self.customer.get().strip())
            self.output.delete("1.0", "end")
            self.output.insert("1.0", token)
        except Exception as error:
            messagebox.showerror("Gerar key", "Não foi possível emitir. Confira a senha, a pasta e os dados.\n" + str(error))

    def copy(self):
        token = self.output.get("1.0", "end").strip()
        if token:
            self.clipboard_clear()
            self.clipboard_append(token)


if __name__ == "__main__":
    window = Admin()
    if "--smoke-test" in sys.argv:
        window.update()
        window.destroy()
    else:
        window.mainloop()
