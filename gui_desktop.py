import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from config import ensure_dirs, load_config, setup_logging
from mailer import MailStats, run_campaign
from smtp_checker import check_smtps
from recipient_ops import sample_recipients, save_recipients
from preview import EmailPreview, load_templates_from_files
from campaign_state import list_pending_campaigns, load_campaign_state
from smtp_client import test_smtp


class Tooltip:
    """Tooltip helper for widgets."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.showtip, add="+")
        self.widget.bind("<Leave>", self.hidetip, add="+")

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#313244", highlightthickness=0)
        label = tk.Label(tw, text=self.text, bg="#313244", fg="#cdd6f4",
                        font=("Consolas", 9), padx=4, pady=2, wraplength=200, justify="left")
        label.pack()

    def hidetip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class MailerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mailer Control Panel")
        self.geometry("720x660")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self._config = load_config()
        self._log = setup_logging(self._config["log_file"], self._config["log_level"])

        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._campaign_thread = None
        self._paused = False

        self._build_menu()
        self._build_widgets()

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=False, bg="#313244", fg="#cdd6f4")
        file_menu.add_command(label="Export Config", command=self._export_config)
        file_menu.add_command(label="Import Config", command=self._import_config)
        file_menu.add_separator()
        file_menu.add_command(label="View Campaign History", command=self._show_history)
        menubar.add_cascade(label="File", menu=file_menu)

    def _export_config(self):
        """Save current GUI settings to a JSON file."""
        cfg = {
            "smtps": self._smtps_var.get(),
            "recipients": self._recipients_var.get(),
            "letters": self._letters_var.get(),
            "subjects": self._subjects_var.get(),
            "from_names": self._from_names_var.get(),
            "attachments": self._attachments_var.get(),
            "threads": self._threads_var.get(),
            "delay": self._delay_var.get(),
            "retries": self._retries_var.get(),
            "rate": self._rate_var.get(),
            "domain_limit": self._domain_lim_var.get(),
            "test_mode": self._test_mode_var.get(),
            "sample_count": self._sample_count_var.get(),
        }
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if path:
            Path(path).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            self._log_msg(f"✓ Config exported → {path}")

    def _import_config(self):
        """Load GUI settings from a JSON file."""
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            cfg = json.loads(Path(path).read_text(encoding="utf-8"))
            self._smtps_var.set(cfg.get("smtps", ""))
            self._recipients_var.set(cfg.get("recipients", ""))
            self._letters_var.set(cfg.get("letters", "data/letters"))
            self._subjects_var.set(cfg.get("subjects", "data/subjects.txt"))
            self._from_names_var.set(cfg.get("from_names", "data/from_names.txt"))
            self._attachments_var.set(cfg.get("attachments", ""))
            self._threads_var.set(cfg.get("threads", 10))
            self._delay_var.set(cfg.get("delay", 1.0))
            self._retries_var.set(cfg.get("retries", 1))
            self._rate_var.set(cfg.get("rate", 0))
            self._domain_lim_var.set(cfg.get("domain_limit", 0))
            self._test_mode_var.set(cfg.get("test_mode", False))
            self._sample_count_var.set(cfg.get("sample_count", 10))
            self._log_msg(f"✓ Config imported from {path}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to load config: {e}")

    def _show_history(self):
        """Show a list of past campaign reports."""
        report_dir = Path("results")
        reports = sorted(report_dir.glob("report_*.txt"), reverse=True)
        if not reports:
            messagebox.showinfo("History", "No campaign reports found.")
            return

        win = tk.Toplevel(self)
        win.title("Campaign History")
        win.geometry("700x500")
        win.configure(bg="#1e1e2e")

        frame = tk.Frame(win, bg="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text="Recent campaigns:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Consolas", 11)).pack(anchor="w", pady=(0, 6))

        txt = scrolledtext.ScrolledText(frame, height=20, bg="#11111b", fg="#a6e3a1",
                                        font=("Consolas", 9), bd=0, state="disabled")
        txt.pack(fill="both", expand=True)

        for report_file in reports[:20]:
            txt.configure(state="normal")
            txt.insert("end", f"● {report_file.name}\n")
            try:
                content = report_file.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if line.strip():
                        txt.insert("end", f"  {line}\n")
            except Exception:
                pass
            txt.insert("end", "\n")
            txt.configure(state="disabled")

    # ── Widget construction ───────────────────────────────────────────────────

    def _build_widgets(self):
        PAD = {"padx": 8, "pady": 4}
        BG   = "#1e1e2e"
        FG   = "#cdd6f4"
        ENTRY_BG = "#313244"
        BTN_BG   = "#45475a"
        ACCENT   = "#89b4fa"
        FONT     = ("Consolas", 10)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", background=BTN_BG, foreground=FG,
                         font=FONT, relief="flat", padding=4)
        style.map("TButton", background=[("active", "#585b70")])

        # ── File pickers ──────────────────────────────────────────────────────
        frame_files = tk.LabelFrame(self, text=" Files ", bg=BG, fg=ACCENT,
                                    font=FONT, bd=1, relief="solid")
        frame_files.pack(fill="x", padx=12, pady=(10, 4))

        self._smtps_var        = tk.StringVar()
        self._recipients_var   = tk.StringVar()
        self._letters_var      = tk.StringVar(value="data/letters")
        self._subjects_var     = tk.StringVar(value="data/subjects.txt")
        self._from_names_var   = tk.StringVar(value="data/from_names.txt")
        self._attachments_var  = tk.StringVar()

        file_rows = [
            ("SMTP File",      self._smtps_var,      self._browse_smtps,         None),
            ("Recipients",     self._recipients_var,  self._browse_recipients,    None),
            ("Letters Folder", self._letters_var,     self._browse_letters,       self._select_letters),
            ("Subjects File",  self._subjects_var,    self._browse_subjects,      self._select_subjects),
            ("From-Names File",self._from_names_var,  self._browse_from_names,    None),
            ("Attachments",    self._attachments_var, self._browse_attachments,   None),
        ]

        tooltips = {
            "SMTP File": "File containing SMTP credentials (host|port|user|pass)",
            "Recipients": "File containing email addresses (one per line)",
            "Letters Folder": "Folder containing HTML email templates",
            "Subjects File": "File containing email subjects (one per line)",
            "From-Names File": "Display names for From field (one per line)",
            "Attachments": "Files to attach to every email",
        }

        for label, var, browse_cmd, select_cmd in file_rows:
            row = tk.Frame(frame_files, bg=BG)
            row.pack(fill="x", padx=6, pady=2)
            lbl = tk.Label(row, text=f"{label:<16}", bg=BG, fg=FG, font=FONT,
                     width=16, anchor="w")
            lbl.pack(side="left")
            if label in tooltips:
                Tooltip(lbl, tooltips[label])
            tk.Entry(row, textvariable=var, bg=ENTRY_BG, fg=FG,
                     font=FONT, bd=0, insertbackground=FG,
                     width=40).pack(side="left", padx=(4, 4))
            ttk.Button(row, text="Browse", command=browse_cmd, width=8).pack(side="left", padx=2)
            if select_cmd:
                ttk.Button(row, text="Select", command=select_cmd, width=8).pack(side="left")

        # ── Settings row ──────────────────────────────────────────────────────
        frame_settings = tk.Frame(self, bg=BG)
        frame_settings.pack(fill="x", padx=12, pady=4)

        self._threads_var      = tk.IntVar(value=self._config.get("threads", 10))
        self._delay_var        = tk.DoubleVar(value=self._config.get("delay_seconds", 1.0))
        self._retries_var      = tk.IntVar(value=self._config.get("retries", 1))
        self._rate_var         = tk.DoubleVar(value=self._config.get("rate_per_second", 0))
        self._domain_lim_var   = tk.IntVar(value=self._config.get("domain_limit_per_minute", 0))
        self._test_mode_var    = tk.BooleanVar(value=False)
        self._sample_count_var = tk.IntVar(value=10)
        self._selected_subjects = []
        self._selected_letters = []

        for label, var, width in [
            ("Threads:",  self._threads_var,    4),
            ("Delay(s):", self._delay_var,       4),
            ("Retries:",  self._retries_var,     3),
            ("Rate/s:",   self._rate_var,        4),
            ("Dom/min:",  self._domain_lim_var,  4),
        ]:
            tk.Label(frame_settings, text=label, bg=BG, fg=FG,
                     font=FONT).pack(side="left", padx=(0, 2))
            tk.Entry(frame_settings, textvariable=var, bg=ENTRY_BG, fg=FG,
                     font=FONT, bd=0, insertbackground=FG,
                     width=width).pack(side="left", padx=(0, 8))

        test_cb = tk.Checkbutton(frame_settings, text="Test", variable=self._test_mode_var,
                       bg=BG, fg=FG, font=FONT,
                       selectcolor="#313244")
        test_cb.pack(side="left", padx=(0, 4))
        Tooltip(test_cb, "Test mode: Send to first N recipients only")

        tk.Label(frame_settings, text="N:", bg=BG, fg=FG, font=FONT).pack(side="left", padx=(0, 2))
        sample_entry = tk.Entry(frame_settings, textvariable=self._sample_count_var, bg=ENTRY_BG, fg=FG,
                 font=FONT, bd=0, insertbackground=FG,
                 width=3)
        sample_entry.pack(side="left", padx=(0, 14))
        Tooltip(sample_entry, "Number of recipients for test mode")

        ttk.Button(frame_settings, text="Preview Email",
                   command=self._preview_email, width=14).pack(side="right", padx=2)
        ttk.Button(frame_settings, text="Test SMTP",
                   command=self._test_single_smtp, width=12).pack(side="right", padx=2)
        ttk.Button(frame_settings, text="Preview Letter",
                   command=self._preview_letter, width=14).pack(side="right", padx=2)

        # ── Presets row ───────────────────────────────────────────────────────
        frame_presets = tk.Frame(self, bg=BG)
        frame_presets.pack(fill="x", padx=12, pady=4)

        tk.Label(frame_presets, text="Presets:", bg=BG, fg=FG,
                 font=FONT).pack(side="left", padx=(0, 4))
        ttk.Button(frame_presets, text="High-Speed",
                   command=self._preset_high_speed, width=14).pack(side="left", padx=2)
        ttk.Button(frame_presets, text="Careful",
                   command=self._preset_careful, width=14).pack(side="left", padx=2)
        ttk.Button(frame_presets, text="Balanced",
                   command=self._preset_balanced, width=14).pack(side="left", padx=2)
        ttk.Button(frame_presets, text="View Recipients",
                   command=self._show_recipient_table, width=14).pack(side="left", padx=2)

        self._custom_settings_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_presets, text="Save per-campaign", variable=self._custom_settings_var,
                       bg=BG, fg=FG, font=FONT, selectcolor="#313244").pack(side="left", padx=(20, 0))

        # ── Stats label ───────────────────────────────────────────────────────
        self._stats_label = tk.Label(
            self,
            text="  Sent: 0    Failed: 0    Skipped: 0    Elapsed: 0.0s",
            bg="#181825", fg=ACCENT, font=("Consolas", 11),
            anchor="w", relief="flat", padx=8,
        )
        self._stats_label.pack(fill="x", padx=12, pady=(6, 2))

        # ── Progress bar ──────────────────────────────────────────────────────
        style.configure("Mail.Horizontal.TProgressbar",
                         troughcolor="#313244", background="#89b4fa",
                         borderwidth=0, relief="flat")
        self._progress = ttk.Progressbar(
            self, style="Mail.Horizontal.TProgressbar",
            orient="horizontal", mode="determinate", maximum=100, value=0,
        )
        self._progress.pack(fill="x", padx=12, pady=(0, 4))

        # ── Buttons ───────────────────────────────────────────────────────────
        frame_btns = tk.Frame(self, bg=BG)
        frame_btns.pack(pady=6)

        self._btn_start = ttk.Button(frame_btns, text="  START  ",
                                     command=self.start_campaign, width=12)
        self._btn_pause = ttk.Button(frame_btns, text="  PAUSE  ",
                                     command=self.pause_campaign, width=12,
                                     state="disabled")
        self._btn_stop  = ttk.Button(frame_btns, text="  STOP   ",
                                     command=self.stop_campaign, width=12,
                                     state="disabled")
        self._btn_resume = ttk.Button(frame_btns, text=" RESUME  ",
                                      command=self._show_resume_dialog, width=12,
                                      state="disabled")
        self._btn_check = ttk.Button(frame_btns, text=" TEST SMTPs ",
                                     command=self.test_smtps, width=14)

        self._btn_start.pack(side="left", padx=6)
        self._btn_pause.pack(side="left", padx=6)
        self._btn_stop.pack(side="left", padx=6)
        self._btn_resume.pack(side="left", padx=6)
        self._btn_check.pack(side="left", padx=14)

        # Enable resume button if there are pending campaigns
        self._check_pending_campaigns()

        # ── Log box ───────────────────────────────────────────────────────────
        self._log_box = scrolledtext.ScrolledText(
            self, height=10, bg="#11111b", fg="#a6e3a1",
            font=("Consolas", 9), bd=0, state="disabled",
            insertbackground=FG,
        )
        self._log_box.pack(fill="both", expand=True, padx=12, pady=(2, 10))

    # ── Browse helpers ────────────────────────────────────────────────────────

    def _browse_smtps(self):
        p = filedialog.askopenfilename(title="Select SMTP file",
                                       filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if p:
            self._smtps_var.set(p)

    def _browse_recipients(self):
        p = filedialog.askopenfilename(title="Select recipients file",
                                       filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if p:
            self._recipients_var.set(p)

    def _browse_letters(self):
        p = filedialog.askdirectory(title="Select letters folder")
        if p:
            self._letters_var.set(p)

    def _browse_subjects(self):
        p = filedialog.askopenfilename(title="Select subjects file",
                                       filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if p:
            self._subjects_var.set(p)

    def _browse_from_names(self):
        p = filedialog.askopenfilename(title="Select from-names file",
                                       filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if p:
            self._from_names_var.set(p)

    def _browse_attachments(self):
        paths = filedialog.askopenfilenames(title="Select attachment files")
        if paths:
            self._attachments_var.set(";".join(paths))

    # ── Subject selector ──────────────────────────────────────────────────────

    def _select_subjects(self):
        subjects_path = self._subjects_var.get().strip()
        if not subjects_path or not Path(subjects_path).exists():
            messagebox.showwarning("Select Subjects", "Set subjects file path first.")
            return

        # Load all subjects
        all_subjects = [l.strip() for l in Path(subjects_path).read_text(encoding="utf-8").splitlines()
                        if l.strip() and not l.startswith("#")]
        if not all_subjects:
            messagebox.showinfo("Select Subjects", "No subjects found in file.")
            return

        # Create selector window
        win = tk.Toplevel(self)
        win.title("Select Subjects to Use")
        win.geometry("400x400")
        win.configure(bg="#1e1e2e")

        tk.Label(win, text="Select which subjects to use:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Consolas", 10)).pack(anchor="w", padx=10, pady=(10, 4))

        frame = tk.Frame(win, bg="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=10, pady=4)

        canvas = tk.Canvas(frame, bg="#11111b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollframe = tk.Frame(canvas, bg="#11111b")

        scrollframe.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollframe, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        vars = []
        for subj in all_subjects:
            var = tk.BooleanVar(value=(subj in self._selected_subjects) if self._selected_subjects else True)
            cb = tk.Checkbutton(scrollframe, text=subj, variable=var, bg="#11111b", fg="#a6e3a1",
                               selectcolor="#313244", font=("Consolas", 9))
            cb.pack(anchor="w")
            vars.append((subj, var))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _save():
            self._selected_subjects = [subj for subj, var in vars if var.get()]
            if self._selected_subjects:
                self._log_msg(f"Selected {len(self._selected_subjects)} subjects: {', '.join(self._selected_subjects[:3])}...")
            else:
                messagebox.showwarning("Select Subjects", "Select at least one subject.")
                return
            win.destroy()

        def _delete_selected():
            """Delete selected subjects from file."""
            to_delete = [subj for subj, var in vars if var.get()]
            if not to_delete:
                messagebox.showwarning("Delete", "Select subjects to delete first.")
                return

            subjects_str = "\n  ".join(to_delete)
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Delete {len(to_delete)} subject(s)?\n\n  {subjects_str}\n\nThis cannot be undone!"
            )

            if not confirm:
                return

            # Read current file and remove selected subjects
            subjects_path = self._subjects_var.get().strip()
            if not subjects_path or not Path(subjects_path).exists():
                messagebox.showerror("Error", "Subjects file not found.")
                return

            try:
                with open(subjects_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Keep lines that are comments or not in the delete list
                kept_lines = []
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#') or stripped not in to_delete:
                        kept_lines.append(line)

                with open(subjects_path, 'w', encoding='utf-8') as f:
                    f.writelines(kept_lines)

                self._log_msg(f"Deleted {len(to_delete)} subject(s) from file")
                win.destroy()
                # Refresh the selector
                self.after(100, self._select_subjects)
            except Exception as e:
                messagebox.showerror("Delete Error", f"Could not delete subjects: {e}")

        # Button frame
        btn_frame = tk.Frame(win, bg="#1e1e2e")
        btn_frame.pack(fill="x", padx=10, pady=8)

        tk.Button(btn_frame, text="Delete", command=_delete_selected, bg="#f38ba8", fg="#1e1e2e",
                 font=("Consolas", 10), width=10).pack(side="left", padx=2)
        tk.Button(btn_frame, text="OK", command=_save, bg="#45475a", fg="#cdd6f4",
                 font=("Consolas", 10), width=10).pack(side="right", padx=2)

    # ── Letter selector ───────────────────────────────────────────────────────

    def _select_letters(self):
        letters_path = self._letters_var.get().strip() or "data/letters"
        letters_files = sorted(Path(letters_path).glob("*.html"))
        if not letters_files:
            messagebox.showinfo("Select Letters", f"No .html files found in {letters_path}")
            return

        # Create selector window
        win = tk.Toplevel(self)
        win.title("Select Letter Templates to Use")
        win.geometry("400x350")
        win.configure(bg="#1e1e2e")

        tk.Label(win, text="Select which templates to use:", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Consolas", 10)).pack(anchor="w", padx=10, pady=(10, 4))

        frame = tk.Frame(win, bg="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=10, pady=4)

        canvas = tk.Canvas(frame, bg="#11111b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollframe = tk.Frame(canvas, bg="#11111b")

        scrollframe.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollframe, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        vars = []
        for letter_file in letters_files:
            var = tk.BooleanVar(value=(str(letter_file) in self._selected_letters) if self._selected_letters else True)
            cb = tk.Checkbutton(scrollframe, text=letter_file.name, variable=var, bg="#11111b", fg="#a6e3a1",
                               selectcolor="#313244", font=("Consolas", 9))
            cb.pack(anchor="w")
            vars.append((str(letter_file), var))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _save():
            self._selected_letters = [path for path, var in vars if var.get()]
            if self._selected_letters:
                self._log_msg(f"Selected {len(self._selected_letters)} templates: {', '.join(Path(p).name for p in self._selected_letters[:3])}...")
            else:
                messagebox.showwarning("Select Letters", "Select at least one template.")
                return
            win.destroy()

        def _delete_selected():
            """Delete selected letter templates."""
            to_delete = [path for path, var in vars if var.get()]
            if not to_delete:
                messagebox.showwarning("Delete", "Select templates to delete first.")
                return

            files_str = "\n  ".join(Path(p).name for p in to_delete)
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Delete {len(to_delete)} template(s)?\n\n  {files_str}\n\nThis cannot be undone!"
            )

            if not confirm:
                return

            deleted_count = 0
            for path in to_delete:
                try:
                    Path(path).unlink()
                    deleted_count += 1
                except Exception as e:
                    messagebox.showerror("Delete Error", f"Could not delete {Path(path).name}: {e}")

            if deleted_count > 0:
                self._log_msg(f"Deleted {deleted_count} template(s)")
                win.destroy()
                # Refresh the selector to show remaining templates
                self.after(100, self._select_letters)

        # Button frame
        btn_frame = tk.Frame(win, bg="#1e1e2e")
        btn_frame.pack(fill="x", padx=10, pady=8)

        tk.Button(btn_frame, text="Delete", command=_delete_selected, bg="#f38ba8", fg="#1e1e2e",
                 font=("Consolas", 10), width=10).pack(side="left", padx=2)
        tk.Button(btn_frame, text="OK", command=_save, bg="#45475a", fg="#cdd6f4",
                 font=("Consolas", 10), width=10).pack(side="right", padx=2)

    # ── Letter preview ────────────────────────────────────────────────────────

    def _preview_letter(self):
        folder = self._letters_var.get().strip() or "data/letters"
        files = sorted(Path(folder).glob("*.html"))
        if not files:
            messagebox.showinfo("Preview", f"No .html files found in:\n{folder}")
            return

        win = tk.Toplevel(self)
        win.title("Letter Preview")
        win.geometry("660x480")
        win.configure(bg="#1e1e2e")

        BG, FG = "#1e1e2e", "#cdd6f4"
        FONT = ("Consolas", 10)

        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 2))

        tk.Label(top, text="File:", bg=BG, fg=FG, font=FONT).pack(side="left")
        file_var = tk.StringVar(value=str(files[0]))
        sel = ttk.Combobox(top, textvariable=file_var, font=FONT, width=50,
                           values=[str(f) for f in files], state="readonly")
        sel.pack(side="left", padx=6)

        txt = scrolledtext.ScrolledText(win, bg="#11111b", fg="#a6e3a1",
                                        font=FONT, bd=0, wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        def _load(event=None):
            p = Path(file_var.get())
            try:
                content = p.read_text(encoding="utf-8")
            except Exception as e:
                content = f"Error reading file: {e}"
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", content)
            txt.configure(state="disabled")

        sel.bind("<<ComboboxSelected>>", _load)
        _load()

    # ── Email preview ─────────────────────────────────────────────────────────

    def _preview_email(self):
        """Preview email as it will be sent (with variable expansion)."""
        subjects_path = self._subjects_var.get().strip() or "data/subjects.txt"
        from_names_path = self._from_names_var.get().strip() or "data/from_names.txt"
        letters_path = self._letters_var.get().strip() or "data/letters"

        try:
            subject, from_name, letter = load_templates_from_files(
                subjects_path, from_names_path, letters_path
            )
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not load templates: {e}")
            return

        win = tk.Toplevel(self)
        win.title("Email Preview")
        win.geometry("700x600")
        win.configure(bg="#1e1e2e")

        BG, FG = "#1e1e2e", "#cdd6f4"
        ENTRY_BG = "#313244"
        FONT = ("Consolas", 10)

        # Test recipient input
        frame_test = tk.Frame(win, bg=BG)
        frame_test.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(frame_test, text="Test Recipient:", bg=BG, fg=FG, font=FONT).pack(side="left", padx=(0, 4))
        recipient_var = tk.StringVar(value="test@example.com")
        tk.Entry(frame_test, textvariable=recipient_var, bg=ENTRY_BG, fg=FG,
                 font=FONT, bd=0, insertbackground=FG, width=40).pack(side="left", padx=(0, 4))

        # Preview button
        def _do_preview():
            recipient = recipient_var.get().strip()
            if not recipient or '@' not in recipient:
                messagebox.showwarning("Preview", "Enter a valid test email address")
                return

            preview = EmailPreview(subject, letter, from_name)
            result = preview.preview_for_recipient(recipient)

            # Update preview windows
            subject_txt.configure(state="normal")
            subject_txt.delete("1.0", "end")
            subject_txt.insert("end", f"Subject: {result['subject']}")
            subject_txt.configure(state="disabled")

            from_txt.configure(state="normal")
            from_txt.delete("1.0", "end")
            from_txt.insert("end", f"From: {result['from_name']}")
            from_txt.configure(state="disabled")

            body_txt.configure(state="normal")
            body_txt.delete("1.0", "end")
            body_txt.insert("end", result['body_html'])
            body_txt.configure(state="disabled")

        ttk.Button(frame_test, text="Refresh Preview", command=_do_preview, width=15).pack(side="left")

        # Subject preview
        tk.Label(win, text="Subject:", bg=BG, fg=FG, font=FONT).pack(anchor="w", padx=10, pady=(4, 0))
        subject_txt = tk.Text(win, height=2, bg="#11111b", fg="#a6e3a1", font=FONT, bd=0)
        subject_txt.pack(fill="x", padx=10, pady=(0, 4))

        # From-name preview
        tk.Label(win, text="From:", bg=BG, fg=FG, font=FONT).pack(anchor="w", padx=10, pady=(4, 0))
        from_txt = tk.Text(win, height=1, bg="#11111b", fg="#a6e3a1", font=FONT, bd=0)
        from_txt.pack(fill="x", padx=10, pady=(0, 4))

        # Body preview
        tk.Label(win, text="Body (HTML):", bg=BG, fg=FG, font=FONT).pack(anchor="w", padx=10, pady=(4, 0))
        body_txt = scrolledtext.ScrolledText(win, height=15, bg="#11111b", fg="#a6e3a1",
                                            font=FONT, bd=0)
        body_txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Initial preview
        _do_preview()

    # ── SMTP test ─────────────────────────────────────────────────────────────

    def _test_single_smtp(self):
        """Test a single SMTP credential."""
        win = tk.Toplevel(self)
        win.title("Test SMTP Connection")
        win.geometry("500x300")
        win.configure(bg="#1e1e2e")

        BG, FG = "#1e1e2e", "#cdd6f4"
        ENTRY_BG = "#313244"
        FONT = ("Consolas", 10)

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Input fields
        fields = [
            ("Host:", "smtp.example.com"),
            ("Port:", "587"),
            ("User:", "email@example.com"),
            ("Password:", ""),
        ]

        vars_dict = {}
        for label, default in fields:
            lbl = tk.Label(frame, text=label, bg=BG, fg=FG, font=FONT, width=10, anchor="w")
            lbl.pack(fill="x", pady=4)

            if "Password" in label:
                var = tk.StringVar(value=default)
                entry = tk.Entry(frame, textvariable=var, bg=ENTRY_BG, fg=FG,
                                font=FONT, bd=0, show="*", insertbackground=FG)
            else:
                var = tk.StringVar(value=default)
                entry = tk.Entry(frame, textvariable=var, bg=ENTRY_BG, fg=FG,
                                font=FONT, bd=0, insertbackground=FG)
            entry.pack(fill="x", pady=(0, 8))
            vars_dict[label.replace(":", "")] = var

        result_txt = tk.Text(frame, height=6, bg="#11111b", fg="#a6e3a1",
                            font=FONT, bd=0, state="disabled")
        result_txt.pack(fill="both", expand=True, pady=(8, 0))

        def _do_test():
            try:
                host = vars_dict["Host"].get().strip()
                port = int(vars_dict["Port"].get().strip())
                user = vars_dict["User"].get().strip()
                password = vars_dict["Password"].get()

                result_txt.configure(state="normal")
                result_txt.delete("1.0", "end")
                result_txt.insert("end", "Testing connection...\n")
                result_txt.configure(state="disabled")
                win.update()

                result = test_smtp(host, port, user, password, smtp_timeout=10)

                result_txt.configure(state="normal")
                result_txt.delete("1.0", "end")
                if result.success:
                    result_txt.insert("end", "✓ SUCCESS\n\n")
                    result_txt.insert("end", result.message, "success")
                else:
                    result_txt.insert("end", "✗ FAILED\n\n")
                    result_txt.insert("end", result.message, "error")
                result_txt.configure(state="disabled")

            except ValueError as e:
                messagebox.showerror("Input Error", f"Invalid port number: {e}")
            except Exception as e:
                messagebox.showerror("Test Error", str(e))

        ttk.Button(frame, text="Test Connection", command=_do_test, width=20).pack(pady=8)

        result_txt.tag_configure("success", foreground="#a6e3a1")
        result_txt.tag_configure("error", foreground="#f38ba8")

    # ── Log widget helper ─────────────────────────────────────────────────────

    def _log_msg(self, message: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    # ── Stats update (must be scheduled via after()) ──────────────────────────

    def _update_stats(self, snapshot: dict):
        total = snapshot.get("total", 0)
        self._stats_label.config(
            text=(
                f"  Sent: {snapshot['sent']:<6}"
                f"Failed: {snapshot['failed']:<6}"
                f"Skipped: {snapshot['skipped']:<6}"
                f"/{total}  "
                f"Elapsed: {snapshot['elapsed']:.1f}s"
            )
        )
        self._progress["value"] = snapshot.get("percent", 0)

    # ── Callbacks from worker threads ─────────────────────────────────────────

    def _on_progress(self, snapshot: dict):
        self.after(0, self._update_stats, snapshot)

    def _on_complete(self, stats: MailStats):
        snap = stats.snapshot()

        def _finish():
            self._update_stats(snap)
            self._progress["value"] = 100
            self._log_msg(
                f"── Campaign finished ──  "
                f"Sent: {snap['sent']}  Failed: {snap['failed']}  "
                f"Skipped: {snap['skipped']}  Elapsed: {snap['elapsed']:.1f}s"
            )
            if snap["reasons"]:
                self._log_msg(f"Failure breakdown: {snap['reasons']}")
            self._btn_start.config(state="normal")
            self._btn_pause.config(state="disabled", text="  PAUSE  ")
            self._btn_stop.config(state="disabled")
            self._paused = False

        self.after(0, _finish)

    # ── Campaign control ──────────────────────────────────────────────────────

    def start_campaign(self):
        smtps = self._smtps_var.get().strip()
        recipients = self._recipients_var.get().strip()

        if not smtps:
            self.after(0, self._log_msg, "ERROR: SMTP file path is required.")
            return
        if not recipients:
            self.after(0, self._log_msg, "ERROR: Recipients file path is required.")
            return

        cfg = dict(self._config)
        try:
            cfg["threads"]               = max(1, min(int(self._threads_var.get()), 100))
            cfg["delay_seconds"]         = max(0.0, float(self._delay_var.get()))
            cfg["retries"]               = max(0, min(int(self._retries_var.get()), 10))
            cfg["rate_per_second"]       = max(0.0, float(self._rate_var.get()))
            cfg["domain_limit_per_minute"] = max(0, int(self._domain_lim_var.get()))
        except (ValueError, tk.TclError):
            self._log_msg("ERROR: Invalid setting value (threads/delay/retries/rate/domain).")
            return

        raw_attach = self._attachments_var.get().strip()
        attachments = [p for p in raw_attach.split(";") if p.strip()] if raw_attach else []

        recipients_to_use = recipients
        test_mode = self._test_mode_var.get()
        sample_count = 0
        if test_mode:
            try:
                from .core.mailer import load_recipients
                from .core.recipient_ops import sample_recipients, save_recipients
                all_recipients = load_recipients(recipients)
                sample_count = max(1, min(int(self._sample_count_var.get()), len(all_recipients)))
                sampled = sample_recipients(all_recipients, sample_count)
                temp_recipients_file = Path("results/.sample_recipients.txt")
                save_recipients(sampled, temp_recipients_file)
                recipients_to_use = str(temp_recipients_file)
            except Exception as e:
                self._log_msg(f"ERROR: Failed to load recipients: {e}")
                return

        self._pause_event.set()
        self._stop_event.clear()
        self._paused = False
        self._progress["value"] = 0

        self._btn_start.config(state="disabled")
        self._btn_pause.config(state="normal", text="  PAUSE  ")
        self._btn_stop.config(state="normal")

        mode_str = f"[TEST MODE - {sample_count} recipients] " if test_mode else ""
        self._log_msg(
            f"Starting {mode_str}"
            f"Threads:{cfg['threads']}  Delay:{cfg['delay_seconds']}s  "
            f"Retries:{cfg['retries']}  Rate:{cfg['rate_per_second']}/s  "
            f"DomLim:{cfg['domain_limit_per_minute']}/min"
        )
        if attachments:
            self._log_msg(f"Attachments: {', '.join(Path(a).name for a in attachments)}")

        paths = {
            "smtps": smtps,
            "recipients": recipients_to_use,
            "subjects": self._subjects_var.get().strip() or "data/subjects.txt",
            "from_names": self._from_names_var.get().strip() or "data/from_names.txt",
            "letters": self._letters_var.get().strip() or "data/letters",
        }

        self._campaign_thread = threading.Thread(
            target=self._run_in_thread, args=(cfg, paths, attachments), daemon=True
        )
        self._campaign_thread.start()

    def _run_in_thread(self, config: dict, paths: dict, attachments: list):
        try:
            run_campaign(
                recipients_path=paths["recipients"],
                smtps_path=paths["smtps"],
                subjects_path=paths["subjects"],
                from_names_path=paths["from_names"],
                letters_folder=paths["letters"],
                config=config,
                pause_event=self._pause_event,
                stop_event=self._stop_event,
                attachments=attachments,
                selected_subjects=self._selected_subjects if self._selected_subjects else None,
                selected_letters=self._selected_letters if self._selected_letters else None,
                progress_callback=self._on_progress,
                completion_callback=self._on_complete,
            )
        except Exception as e:
            self.after(0, self._log_msg, f"FATAL: {e}")
            self.after(0, lambda: self._btn_start.config(state="normal"))
            self.after(0, lambda: self._btn_pause.config(state="disabled"))
            self.after(0, lambda: self._btn_stop.config(state="disabled"))

    def test_smtps(self):
        smtps = self._smtps_var.get().strip()
        if not smtps:
            self._log_msg("ERROR: Set the SMTP file path first.")
            return

        self._btn_check.config(state="disabled")
        self._btn_start.config(state="disabled")
        self._log_msg(f"Testing SMTPs in: {smtps} …")

        stop_ev = threading.Event()

        def _progress(checked, total, valid):
            pct = checked / total * 100 if total else 0
            self.after(0, self._progress.configure, {"value": pct})
            self.after(0, self._log_msg,
                       f"  [{checked}/{total}] valid so far: {valid}")

        def _run():
            try:
                valid = check_smtps(
                    smtps,
                    threads=20,
                    timeout=self._config.get("smtp_timeout", 10),
                    save_valid=True,
                    progress_callback=_progress,
                    stop_event=stop_ev,
                )
                out = str(Path(smtps).with_suffix(".checked.txt"))

                def _done():
                    self._progress["value"] = 100
                    self._log_msg(
                        f"✓ SMTP check done — {len(valid)} valid.  "
                        f"Saved → {out}"
                    )
                    self._smtps_var.set(out)
                    self._btn_check.config(state="normal")
                    self._btn_start.config(state="normal")

                self.after(0, _done)
            except Exception as e:
                self.after(0, self._log_msg, f"SMTP check error: {e}")
                self.after(0, lambda: self._btn_check.config(state="normal"))
                self.after(0, lambda: self._btn_start.config(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    def pause_campaign(self):
        if not self._paused:
            self._pause_event.clear()
            self._paused = True
            self._btn_pause.config(text=" RESUME  ")
            self._log_msg("Campaign paused.")
        else:
            self._pause_event.set()
            self._paused = False
            self._btn_pause.config(text="  PAUSE  ")
            self._log_msg("Campaign resumed.")

    def stop_campaign(self):
        self._stop_event.set()
        self._pause_event.set()
        self._log_msg("Stop requested — waiting for workers to finish...")

    def _check_pending_campaigns(self):
        """Check if there are incomplete campaigns to resume."""
        results_dir = Path("results")
        pending = list_pending_campaigns(results_dir)
        if pending:
            self._btn_resume.config(state="normal")
            self._log_msg(f"ℹ {len(pending)} pending campaign(s) available to resume")
        else:
            self._btn_resume.config(state="disabled")

    def _show_resume_dialog(self):
        """Show dialog to select a campaign to resume."""
        results_dir = Path("results")
        pending = list_pending_campaigns(results_dir)

        if not pending:
            messagebox.showinfo("Resume Campaign", "No pending campaigns found.")
            return

        win = tk.Toplevel(self)
        win.title("Resume Campaign")
        win.geometry("500x300")
        win.configure(bg="#1e1e2e")

        BG, FG = "#1e1e2e", "#cdd6f4"
        FONT = ("Consolas", 10)

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text="Select a campaign to resume:", bg=BG, fg=FG, font=FONT).pack(anchor="w", pady=(0, 6))

        # Listbox of pending campaigns
        listbox = tk.Listbox(frame, bg="#11111b", fg="#a6e3a1", font=FONT, bd=0)
        listbox.pack(fill="both", expand=True, pady=(0, 8))

        for state in pending:
            progress_str = f"{state.progress_percent:.1f}%"
            elapsed_str = f"{state.elapsed_seconds:.0f}s"
            label = f"{state.campaign_id}  [{progress_str}  {elapsed_str} elapsed]"
            listbox.insert("end", label)

        selected_campaign = [None]

        def _resume():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Resume", "Please select a campaign.")
                return
            selected_campaign[0] = pending[sel[0]]
            win.destroy()
            self._log_msg(f"Resuming campaign: {selected_campaign[0].campaign_id} ({selected_campaign[0].progress_percent:.1f}% complete)")

        ttk.Button(frame, text="Resume Selected", command=_resume, width=20).pack(pady=(0, 4))
        ttk.Button(frame, text="Cancel", command=win.destroy, width=20).pack()

    # ── Settings presets ──────────────────────────────────────────────────────

    def _preset_high_speed(self):
        """Load high-speed preset: many threads, short delay, fewer retries."""
        self._threads_var.set(20)
        self._delay_var.set(0.2)
        self._retries_var.set(1)
        self._rate_var.set(0)
        self._domain_lim_var.set(0)
        self._log_msg("PRESET: High-Speed (20 threads, 0.2s delay)")

    def _preset_careful(self):
        """Load careful preset: few threads, long delay, more retries."""
        self._threads_var.set(5)
        self._delay_var.set(5.0)
        self._retries_var.set(3)
        self._rate_var.set(2.0)
        self._domain_lim_var.set(10)
        self._log_msg("PRESET: Careful (5 threads, 5.0s delay, 3 retries)")

    def _preset_balanced(self):
        """Load balanced preset: moderate settings for most use cases."""
        self._threads_var.set(10)
        self._delay_var.set(1.0)
        self._retries_var.set(2)
        self._rate_var.set(0)
        self._domain_lim_var.set(0)
        self._log_msg("PRESET: Balanced (10 threads, 1.0s delay, 2 retries)")

    # ── Recipient table ──────────────────────────────────────────────────────

    def _show_recipient_table(self):
        """Show loaded recipients in a searchable table."""
        from .core.mailer import load_recipients

        recipients_path = self._recipients_var.get().strip()
        if not recipients_path:
            messagebox.showwarning("Recipients", "Set recipients file path first.")
            return

        try:
            recipients = load_recipients(recipients_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load recipients: {e}")
            return

        win = tk.Toplevel(self)
        win.title("Recipient Preview")
        win.geometry("700x500")
        win.configure(bg="#1e1e2e")

        BG, FG = "#1e1e2e", "#cdd6f4"
        ENTRY_BG = "#313244"
        FONT = ("Consolas", 10)

        # Search frame
        search_frame = tk.Frame(win, bg=BG)
        search_frame.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(search_frame, text="Search:", bg=BG, fg=FG, font=FONT).pack(side="left", padx=(0, 4))
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, bg=ENTRY_BG, fg=FG,
                               font=FONT, bd=0, insertbackground=FG, width=40)
        search_entry.pack(side="left", padx=(0, 8))

        # Stats
        stats_label = tk.Label(search_frame, text=f"Total: {len(recipients)} recipients",
                             bg=BG, fg=FG, font=FONT)
        stats_label.pack(side="left")

        # Table frame
        table_frame = tk.Frame(win, bg=BG)
        table_frame.pack(fill="both", expand=True, padx=10, pady=4)

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side="right", fill="y")

        # Listbox
        listbox = tk.Listbox(table_frame, bg="#11111b", fg="#a6e3a1", font=FONT, bd=0,
                            yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        def _update_list(query=""):
            listbox.delete(0, "end")
            filtered = [r for r in recipients if query.lower() in r.lower()]
            for recipient in filtered:
                listbox.insert("end", recipient)
            stats_label.config(text=f"Showing: {len(filtered)}/{len(recipients)} recipients")

        def _on_search(*args):
            _update_list(search_var.get())

        search_var.trace("w", _on_search)
        _update_list()

        # Bottom buttons
        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _copy_selected():
            sel = listbox.curselection()
            if sel:
                self.after(0, self._log_msg, f"Selected recipient: {recipients[sel[0]]}")
                win.destroy()

        ttk.Button(btn_frame, text="Close", command=win.destroy, width=20).pack(side="right", padx=4)


def launch():
    ensure_dirs()
    app = MailerApp()
    app.mainloop()
