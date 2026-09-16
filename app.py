import json
import queue
import sys
import time
import tkinter as tk
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from macro.engine import Engine, FractionalMotion
from macro.branding import apply_icon
from macro.licensing import (ClockGuard, LicenseError, LicenseSession, PLAN_LABELS,
                             decode, device_id, verify)
from macro.profiles import (CATALOG, Profile, duplicate, load_profiles, save_profiles)
from macro.storage import data_dir, write_json

ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent)
BG, CARD, TEXT, MUTED, ACCENT = "#0b1220", "#162235", "#e8eef7", "#a4b3c8", "#43d9b0"


class App(tk.Tk):
    def __init__(self, autostart=True):
        super().__init__()
        apply_icon(self)
        self.title("Policarpo • Macro Completo V2")
        self.geometry("1060x790")
        self.minsize(960, 750)
        self.configure(bg=BG)
        self.engine = Engine()
        self.session = None
        self.public_key = None
        self.guard = None
        self.device = ""
        self.items = []
        self.selected = 0
        self.closing = False
        self.preview_generation = 0
        self.last_clock_save = 0
        self.fields = {}
        self.status = tk.StringVar(value="PAUSADO")
        self.notice = tk.StringVar(value="Escolha um perfil, ajuste os valores e salve.")
        self.license_status = tk.StringVar(value="Sem licença ativa")
        self._style()
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self.close)
        if autostart:
            self.after(100, self.initialize)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Status.TLabel", foreground=ACCENT, font=("Segoe UI", 13, "bold"))
        style.configure("TButton", background=CARD, padding=(12, 8))
        style.map("TButton", background=[("active", "#274363")])
        style.configure("TEntry", fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=CARD, foreground=TEXT, arrowsize=16)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, padding=(20, 10))
        style.map("TNotebook.Tab", background=[("selected", "#274363")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=32)
        style.configure("Treeview.Heading", background="#274363", foreground=TEXT)
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)

    def _layout(self):
        header = ttk.Frame(self, padding=(24, 16))
        header.pack(fill="x")
        ttk.Label(header, text="MACRO COMPLETO", style="Title.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(side="right")
        ttk.Label(self, text="V2  /  Perfis por operador  /  Licenciamento",
                  style="Muted.TLabel", padding=(26, 0, 0, 12)).pack(anchor="w")
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=24)
        self.profiles_tab = ttk.Frame(self.tabs, padding=16)
        self.license_tab = ttk.Frame(self.tabs, padding=24)
        help_tab = ttk.Frame(self.tabs, padding=24)
        self.tabs.add(self.profiles_tab, text="Perfis e ajustes")
        self.tabs.add(self.license_tab, text="Licença")
        self.tabs.add(help_tab, text="Como testar")
        self.tabs.bind("<<NotebookTabChanged>>", lambda event: self.engine.pause())

        left = ttk.Frame(self.profiles_tab)
        left.pack(side="left", fill="both", expand=True, padx=(0, 20))
        ttk.Label(left, text="SEUS PERFIS", style="Status.TLabel").pack(anchor="w", pady=(0, 8))
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse", height=11)
        self.tree.column("#0", width=310, stretch=True)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.choose)
        row = ttk.Frame(left)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Novo", command=self.new_profile).pack(side="left")
        ttk.Button(row, text="Novo DMR", command=self.new_dmr).pack(side="left", padx=4)
        ttk.Button(row, text="Duplicar", command=self.copy_profile).pack(side="left", padx=4)
        ttk.Button(row, text="Excluir", command=self.delete_profile).pack(side="left")
        row2 = ttk.Frame(left)
        row2.pack(fill="x")
        ttk.Button(row2, text="Importar JSON", command=self.import_profiles).pack(side="left")
        ttk.Button(row2, text="Exportar JSON", command=self.export_profiles).pack(side="left", padx=4)
        ttk.Label(left, text="○ A calibrar    ✓ Calibrado por você\nModelos iniciais: vertical 8, lateral 0.\nNão são valores medidos por arma.",
                  style="Muted.TLabel").pack(anchor="w", pady=12)

        right_panel = ttk.Frame(self.profiles_tab)
        right_panel.pack(side="left", fill="both", expand=True)
        scroller = tk.Canvas(right_panel, bg=BG, highlightthickness=0, width=470)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=scroller.yview)
        scroller.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroller.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(scroller)
        pane = scroller.create_window((0, 0), window=right, anchor="nw")
        right.bind("<Configure>", lambda event: scroller.configure(scrollregion=scroller.bbox("all")))
        scroller.bind("<Configure>", lambda event: scroller.itemconfigure(pane, width=event.width))
        form = ttk.Frame(right)
        form.pack(fill="x")
        labels = [("operator", "Operador"), ("weapon", "Arma"), ("loadout", "Mira / acessórios"),
                  ("vertical", "Vertical (0 a 30)"), ("lateral", "Lateral (−5 a 5)"),
                  ("interval_ms", "Intervalo (ms)"), ("dpi", "DPI do mouse"),
                  ("sensitivity", "Sensibilidade H / V / ADS")]
        for index, (name, label) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=index, column=0, sticky="w", pady=3, padx=(0, 12))
            variable = tk.StringVar()
            self.fields[name] = variable
            if name in ("operator", "weapon"):
                control = ttk.Combobox(form, textvariable=variable, width=27,
                                       values=list(CATALOG) if name == "operator" else [])
                if name == "operator":
                    control.bind("<<ComboboxSelected>>", self.operator_changed)
                else:
                    self.weapon_box = control
            else:
                control = ttk.Entry(form, textvariable=variable, width=30)
            control.grid(row=index, column=1, sticky="ew")
            variable.trace_add("write", lambda *args: self.engine.pause())
        form.columnconfigure(1, weight=1)
        self.calibrated = tk.BooleanVar()
        ttk.Checkbutton(right, text="Testei e calibrei este perfil", variable=self.calibrated,
                        command=self.engine.pause).pack(anchor="w", pady=(10, 4))
        rapid_row = ttk.Frame(right)
        rapid_row.pack(fill="x", pady=4)
        self.rapid_fire = tk.BooleanVar()
        self.fire_cps = tk.StringVar(value="5")
        self.rapid_fire.trace_add("write", lambda *args: self.engine.pause())
        self.fire_cps.trace_add("write", lambda *args: self.engine.pause())
        ttk.Checkbutton(rapid_row, text="Rapid Fire (DMR)", variable=self.rapid_fire).pack(side="left")
        ttk.Label(rapid_row, text="Cliques/s:").pack(side="left", padx=(12, 4))
        ttk.Spinbox(rapid_row, from_=1, to=12, increment=0.5,
                    textvariable=self.fire_cps, width=5).pack(side="left")
        ttk.Label(right, text="1–12 cliques/s • ajuste à arma; Novo DMR começa sem compensação.",
                  style="Muted.TLabel").pack(anchor="w")
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Salvar e aplicar", command=self.save_current).pack(side="left")
        ttk.Button(actions, text="Restaurar forças", command=self.reset_forces).pack(side="left", padx=6)
        ttk.Button(right, text="Prévia de 1 segundo (sem mover o mouse)",
                   command=self.preview).pack(fill="x", pady=4)
        self.canvas = tk.Canvas(right, height=100, bg=CARD, highlightthickness=0)
        self.canvas.pack(fill="x", pady=4)
        self.preview_text = ttk.Label(right, text="Prévia ilustra deslocamento, não o recuo do jogo.",
                                      style="Muted.TLabel")
        self.preview_text.pack(anchor="w")
        ttk.Button(right, text="Ativar / pausar  •  F10", command=self.toggle).pack(fill="x", pady=10)

        ttk.Label(self.license_tab, text="LICENÇA DO COMPUTADOR", style="Status.TLabel").pack(anchor="w")
        ttk.Label(self.license_tab, textvariable=self.license_status, wraplength=840).pack(anchor="w", pady=16)
        ttk.Label(self.license_tab, text="Envie este ID ao fornecedor para receber sua key:").pack(anchor="w")
        self.device_text = tk.StringVar()
        ttk.Entry(self.license_tab, textvariable=self.device_text, state="readonly", width=85).pack(fill="x", pady=8)
        ttk.Button(self.license_tab, text="Copiar ID do computador", command=self.copy_device).pack(anchor="w")
        ttk.Label(self.license_tab, text="Cole a nova key abaixo (MCV2.…):").pack(anchor="w", pady=(24, 8))
        self.key_box = tk.Text(self.license_tab, height=5, bg=CARD, fg=TEXT, insertbackground=TEXT, wrap="char")
        self.key_box.pack(fill="x")
        ttk.Button(self.license_tab, text="Ativar / renovar licença", command=self.activate).pack(anchor="w", pady=12)
        ttk.Label(self.license_tab,
                  text="Diária: 24h  •  Semanal: 7 dias  •  Mensal: 30 dias  •  Lifetime: sem vencimento\n"
                       "A validade começa na emissão. Reutilizar uma key não renova o prazo.",
                  style="Muted.TLabel").pack(anchor="w", pady=12)

        help_text = (
            "1. Abra a aba Licença, copie o ID e solicite sua key.\n\n"
            "2. Selecione um operador/arma. Para outro personagem, clique em Novo e preencha os nomes.\n"
            "   Registre DPI, sensibilidade e acessórios; estes campos são anotações, não alteram o jogo.\n\n"
            "3. Ajuste as forças. Lateral negativo move à esquerda; positivo, à direita.\n"
            "   Salve e use a prévia para verificar o sentido e a intensidade relativa.\n\n"
            "4. F10 ativa/pausa. O movimento exige os botões esquerdo e direito pressionados juntos.\n"
            "   Após ativar, solte e pressione os botões novamente. INSERT pausa imediatamente.\n\n"
            "DMR: use Novo DMR ou marque Rapid Fire. Ajuste Cliques/s, salve e segure os dois botões.\n"
            "O ritmo configurado não garante a cadência aceita pela arma.\n\n"
            "5. Trocar de perfil, editar, mudar de aba ou renovar a licença pausa a execução.\n"
            "   A licença é verificada durante a execução, inclusive se a interface estiver ocupada.\n\n"
            "6. Valide os valores no seu Windows e marque o perfil como calibrado somente após testar.\n"
            "   Não há detecção automática de personagem, janela do jogo ou acessórios.\n"
            "   Quando ativado, o movimento é global. Pause com F10 antes de trocar de aplicativo.\n\n"
            "Perfis e licença ficam em %LOCALAPPDATA%\\PolicarpoMacroV2.\n"
            "Para renovar, envie o ID ao fornecedor e cole a nova key na aba Licença."
        )
        ttk.Label(help_tab, text=help_text, wraplength=900, justify="left").pack(anchor="w")
        footer = ttk.Frame(self, padding=(24, 12))
        footer.pack(fill="x")
        ttk.Label(footer, text="Feito por Policarpo", style="Status.TLabel").pack(anchor="e")
        ttk.Label(footer, textvariable=self.notice, wraplength=980, style="Muted.TLabel").pack(anchor="w")

    def initialize(self):
        try:
            self.folder = data_dir()
            self.profile_path = self.folder / "profiles.json"
            self.license_path = self.folder / "license.json"
            self.items = load_profiles(self.profile_path)
            self.refresh(0)
            self.device = device_id()
            self.device_text.set(self.device)
            self.guard = ClockGuard(self.folder / "clock.json")
            self.guard.check()
            self.guard.save()
            self.engine.start()
            if self.engine.error:
                self.notice.set(self.engine.error)
            self.load_public_key()
            if self.license_path.exists():
                raw = json.loads(self.license_path.read_text(encoding="utf-8"))
                self.install_license(raw["token"], persist=False)
        except Exception as error:
            self.engine.pause()
            self.license_status.set(str(error))
            self.notice.set(str(error))
        self.after(100, self.poll)

    def load_public_key(self):
        path = ROOT / "public_key.txt"
        if not path.exists():
            raise LicenseError("O pacote está incompleto. Extraia todos os arquivos do ZIP recebido "
                               "ou solicite um novo pacote ao fornecedor.")
        try:
            self.public_key = decode(path.read_text(encoding="ascii").strip())
            if len(self.public_key) != 32:
                raise ValueError()
        except (ValueError, OSError) as error:
            raise LicenseError("public_key.txt inválido. Solicite o arquivo correto ao fornecedor.") from error

    def refresh(self, index):
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), text=item.label)
        self.selected = max(0, min(index, len(self.items) - 1))
        if self.items:
            self.tree.selection_set(str(self.selected))
            self.tree.see(str(self.selected))
            self.fill(self.items[self.selected])

    def fill(self, profile):
        self.engine.set_profile(profile)
        self.preview_generation += 1
        self.canvas.delete("all")
        for name, variable in self.fields.items():
            variable.set(str(getattr(profile, name)))
        self.calibrated.set(profile.calibrated)
        self.rapid_fire.set(profile.rapid_fire)
        self.fire_cps.set(str(profile.fire_cps))
        self.weapon_box["values"] = CATALOG.get(profile.operator, [])
        self.notice.set("Perfil carregado. Ajustes só são gravados em Salvar e aplicar.")

    def choose(self, event=None):
        selection = self.tree.selection()
        if selection:
            self.selected = int(selection[0])
            self.fill(self.items[self.selected])

    def operator_changed(self, event=None):
        self.weapon_box["values"] = CATALOG.get(self.fields["operator"].get(), [])

    def read_form(self):
        if not self.items:
            raise ValueError("Não há perfis carregados. Corrija o arquivo de perfis e reinicie.")
        values = {name: variable.get().strip() for name, variable in self.fields.items()}
        for name in ("vertical", "lateral", "interval_ms"):
            values[name] = float(values[name].replace(",", "."))
        values["dpi"] = int(values["dpi"])
        return Profile(id=self.items[self.selected].id,
                       calibrated=self.calibrated.get(), rapid_fire=self.rapid_fire.get(),
                       fire_cps=float(self.fire_cps.get().replace(",", ".")), **values).validate()

    def commit_items(self, items, index):
        save_profiles(self.profile_path, items)
        self.items = items
        self.refresh(index)

    def save_current(self):
        self.engine.pause()
        try:
            item = self.read_form()
            updated = list(self.items)
            updated[self.selected] = item
            self.commit_items(updated, self.selected)
            self.notice.set("Perfil salvo e aplicado. Pressione F10 para ativar.")
        except Exception as error:
            messagebox.showerror("Não foi possível salvar", str(error))

    def new_profile(self):
        self.engine.pause()
        try:
            item = duplicate(Profile("new", "Novo operador", "Nova arma"))
            item = replace(item, loadout="Padrão")
            self.commit_items(self.items + [item], len(self.items))
        except Exception as error:
            messagebox.showerror("Novo perfil", str(error))

    def copy_profile(self):
        self.engine.pause()
        try:
            self.commit_items(self.items + [duplicate(self.read_form())], len(self.items))
        except Exception as error:
            messagebox.showerror("Duplicar", str(error))

    def new_dmr(self):
        self.engine.pause()
        try:
            item = duplicate(Profile("new", "Novo operador", "DMR",
                                     vertical=0, rapid_fire=True, fire_cps=5))
            self.commit_items(self.items + [replace(item, loadout="Padrão")], len(self.items))
            self.notice.set("DMR criado: Rapid Fire a 5 cliques/s. Informe operador/arma, ajuste e salve.")
        except Exception as error:
            messagebox.showerror("Novo DMR", str(error))

    def delete_profile(self):
        self.engine.pause()
        if len(self.items) <= 1:
            messagebox.showinfo("Perfis", "Mantenha pelo menos um perfil.")
            return
        if messagebox.askyesno("Excluir", "Excluir o perfil selecionado?"):
            try:
                self.commit_items([p for i, p in enumerate(self.items) if i != self.selected], 0)
            except Exception as error:
                messagebox.showerror("Excluir", str(error))

    def reset_forces(self):
        self.engine.pause()
        for name, value in (("vertical", "8"), ("lateral", "0"), ("interval_ms", "9")):
            self.fields[name].set(value)
        self.calibrated.set(False)
        self.notice.set("Forças restauradas ao modelo inicial. Clique em Salvar e aplicar.")

    def import_profiles(self):
        self.engine.pause()
        path = filedialog.askopenfilename(filetypes=[("Perfis JSON", "*.json")])
        if not path:
            return
        try:
            items = load_profiles(Path(path))
            if messagebox.askyesno("Importar", "Substituir os perfis atuais pelos perfis deste arquivo?"):
                self.commit_items(items, 0)
        except Exception as error:
            messagebox.showerror("Importar", str(error))

    def export_profiles(self):
        self.engine.pause()
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="meus-perfis.json",
                                          filetypes=[("Perfis JSON", "*.json")])
        if path:
            try:
                save_profiles(Path(path), self.items)
                self.notice.set("Perfis salvos exportados. Edite e salve antes de exportar alterações.")
            except Exception as error:
                messagebox.showerror("Exportar", str(error))

    def preview(self):
        self.engine.pause()
        try:
            profile = self.read_form()
        except ValueError as error:
            messagebox.showerror("Prévia", str(error))
            return
        self.preview_generation += 1
        generation = self.preview_generation
        self.canvas.delete("all")
        steps = max(1, round(1000 / profile.interval_ms))
        motion = FractionalMotion()
        total_x = total_y = 0
        width = max(100, self.canvas.winfo_width())
        scale = min(0.4, 75 / max(1, profile.vertical * steps))
        px, py = width / 2, 10
        self.canvas.create_line(px, 0, px, 100, fill="#35516d", dash=(3, 3))
        def tick(index=0):
            nonlocal px, py, total_x, total_y
            if self.closing or generation != self.preview_generation:
                return
            x, y = motion.step(profile.lateral, profile.vertical)
            total_x += x
            total_y += y
            nx, ny = px + x * scale, py + y * scale
            self.canvas.create_line(px, py, nx, ny, fill=ACCENT, width=2)
            px, py = nx, ny
            if index + 1 < steps:
                self.after(max(1, round(profile.interval_ms)), tick, index + 1)
            else:
                self.preview_text.configure(text=f"1s nominal: X={total_x}, Y={total_y} • escala visual {scale:.2f}")
        tick()

    def copy_device(self):
        if self.device:
            self.clipboard_clear()
            self.clipboard_append(self.device)
            self.notice.set("ID copiado. Envie ao fornecedor da licença.")

    def install_license(self, token, persist):
        self.engine.pause()
        if not self.device or self.guard is None:
            raise LicenseError("Identificação/relógio indisponível. Corrija o erro inicial e reinicie.")
        self.load_public_key()
        self.guard.check()
        license = verify(token, self.public_key, self.device)
        self.guard.save()
        if persist:
            write_json(self.license_path, {"token": token})
        self.session = LicenseSession(license)
        self.engine.set_session(self.session)
        self.update_license_label()

    def activate(self):
        self.engine.pause()
        try:
            token = "".join(self.key_box.get("1.0", "end").split())
            self.install_license(token, persist=True)
            self.key_box.delete("1.0", "end")
            self.notice.set("Licença ativada. Selecione um perfil e pressione F10.")
        except Exception as error:
            messagebox.showerror("Ativação", str(error))

    def update_license_label(self):
        if not self.session:
            return
        license = self.session.license
        end = ("Sem vencimento" if license.expires_at is None else
               "Vence em " + datetime.fromtimestamp(license.expires_at).astimezone().strftime("%d/%m/%Y %H:%M:%S %Z"))
        self.license_status.set(f"{PLAN_LABELS[license.plan]} • {license.customer}\n{end}")

    def toggle(self):
        try:
            if self.engine.enabled:
                self.engine.pause()
            else:
                if self.tabs.select() != str(self.profiles_tab):
                    raise ValueError("Abra a aba Perfis e ajustes para ativar.")
                if self.read_form() != self.items[self.selected]:
                    raise ValueError("Salve os ajustes antes de ativar.")
                if self.guard is None:
                    raise LicenseError("Relógio indisponível.")
                self.guard.check()
                self.engine.toggle()
        except Exception as error:
            self.engine.pause()
            self.notice.set(str(error))

    def poll(self):
        if self.closing:
            return
        try:
            while True:
                event = self.engine.events.get_nowait()
                if event == "toggle":
                    self.toggle()
                elif event == "stop":
                    self.notice.set("Pausado pelo INSERT.")
                elif event == "expired":
                    self.notice.set("Licença expirada ou relógio alterado. Abra a aba Licença.")
                elif event == "error":
                    self.notice.set("Motor interrompido: " + self.engine.error)
        except queue.Empty:
            pass
        try:
            if self.guard:
                self.guard.check()
                if time.monotonic() - self.last_clock_save >= 30:
                    self.guard.save()
                    self.last_clock_save = time.monotonic()
            if self.session and not self.session.valid():
                self.engine.set_session(None)
                self.session = None
                self.license_status.set("Licença expirada ou relógio alterado. Corrija o relógio ou solicite uma nova key.")
                self.notice.set("Execução bloqueada. Abra a aba Licença.")
        except Exception as error:
            self.engine.set_session(None)
            self.session = None
            self.license_status.set(str(error))
        self.status.set("ATIVADO • F10 PARA PAUSAR" if self.engine.enabled else "PAUSADO")
        self.after(100, self.poll)

    def close(self):
        self.closing = True
        self.preview_generation += 1
        self.engine.close()
        if self.guard:
            try:
                self.guard.check()
                self.guard.save()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        import tempfile
        import pynput.keyboard
        import pynput.mouse
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = lambda: Path(temporary)
            window = App(autostart=False)
            try:
                window.initialize()
                window.update()
                assert window.items and window.device and window.engine.available
                assert not window.engine.enabled
            finally:
                window.close()
    else:
        App().mainloop()
