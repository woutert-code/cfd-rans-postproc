"""Interactief startscherm voor cfd_postproc.

Dunne tkinter-schil boven case_runner.process_case(): de gebruiker kiest een
CFD-case map, start de postprocessing en ziet live de log plus na afloop de
resultaten (weerstand, frontaal oppervlak, CD, CdA) in een tabel. Figuren en
het logbestand worden weggeschreven naar output-custom in de case-map, maar
niet geopend.

Starten: dubbelklik start.bat in de repo-root, of:

    py -m src.cfd_postproc.gui
"""

from __future__ import annotations

import csv
import logging
import os
import queue
import sys
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:  # tkinter zit standaard in Python op Windows
    tk = None

from . import case_runner
from .__main__ import DEFAULT_SLICE_X

# Kolommen van results.csv die in het scherm getoond worden: (csv-sleutel, titel)
RESULT_COLUMNS = [
    ("patch", "patch"),
    ("weerstand_N", "weerstand [N]"),
    ("frontaal_oppervlak_m2", "frontaal oppervlak [m²]"),
    ("CD", "CD"),
    ("CdA_m2", "CdA [m²]"),
]


# polyMesh-bestanden die aanwezig moeten zijn vóór een run start
POLYMESH_FILES = ("points", "faces", "owner", "neighbour", "boundary")


def missing_polymesh_files(case_dir):
    """Namen van ontbrekende polyMesh-bestanden (lege lijst = mesh compleet)."""
    pm = os.path.join(case_dir, "constant", "polyMesh")
    return [n for n in POLYMESH_FILES if not os.path.isfile(os.path.join(pm, n))]


def parse_positions(text, default):
    """Komma-gescheiden float-lijst; lege tekst geeft de default terug."""
    text = (text or "").strip()
    if not text:
        return list(default)
    return [float(s.strip()) for s in text.split(",") if s.strip()]


def build_kwargs(case_dir, slice_y_text, slice_x_text, overwrite):
    """Zet de invoervelden van het scherm om naar process_case-argumenten.

    Alleen de essentiële velden uit het scherm; de overige parameters
    (atleetpatches, rho, u-ref, tijdmap, strookdikte) vallen terug op de
    standaardwaarden van process_case (u-ref = u_inlet uit system/Variables,
    tijdmap = laatst weggeschreven). Afwijkende waarden gaan via de CLI.
    """
    return {
        "case_dir": case_dir,
        "slice_y": parse_positions(slice_y_text, [0.0]),
        "slice_x": parse_positions(
            slice_x_text, [float(s) for s in DEFAULT_SLICE_X.split(",")]
        ),
        "overwrite": bool(overwrite),
    }


def read_results_table(csv_path):
    """Lees results.csv -> (kolomtitels, rijen) voor de resultatentabel."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    headers = [label for _, label in RESULT_COLUMNS]
    table = [[r.get(key, "") for key, _ in RESULT_COLUMNS] for r in rows]
    return headers, table


class _QueueHandler(logging.Handler):
    """Stuurt geformatteerde logregels naar een queue; het scherm leest die
    in de hoofdthread (tkinter is niet thread-safe)."""

    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


class PostprocApp:
    def __init__(self, root):
        self.root = root
        root.title("cfd-rans-postproc — postprocessing CFD-case")
        root.minsize(780, 580)

        self.case_var = tk.StringVar()
        self.slice_y_var = tk.StringVar(value="0.0")
        self.slice_x_var = tk.StringVar(value=DEFAULT_SLICE_X)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Kies een CFD-case map en klik Start.")
        self.output_var = tk.StringVar(value="")

        self._log_queue = queue.Queue()
        self._build_widgets()

    def _build_widgets(self):
        pad = {"padx": 4, "pady": 2}
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="CFD-case map:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.case_var, width=58).grid(
            row=0, column=1, sticky="ew", **pad
        )
        ttk.Button(frm, text="Bladeren...", command=self._browse).grid(
            row=0, column=2, **pad
        )

        ttk.Label(frm, text="Slice y [m]:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.slice_y_var, width=20).grid(
            row=1, column=1, sticky="w", **pad
        )
        ttk.Label(frm, text="Slice x [m]:").grid(row=1, column=2, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.slice_x_var, width=30).grid(
            row=1, column=3, sticky="w", **pad
        )

        ttk.Checkbutton(
            frm,
            text="Bestaande output-custom overschrijven",
            variable=self.overwrite_var,
        ).grid(row=2, column=0, columnspan=4, sticky="w", **pad)

        self.start_btn = ttk.Button(
            frm, text="Start postprocessing", command=self._start
        )
        self.start_btn.grid(row=3, column=0, sticky="w", pady=(6, 2))
        ttk.Label(frm, textvariable=self.status_var).grid(
            row=3, column=1, columnspan=3, sticky="w", **pad
        )

        ttk.Label(frm, text="Log:").grid(row=4, column=0, sticky="nw", **pad)
        self.log_text = scrolledtext.ScrolledText(
            frm, height=10, width=90, state="disabled"
        )
        self.log_text.grid(row=5, column=0, columnspan=4, sticky="nsew", **pad)
        self.log_text.tag_config("WARNING", foreground="#b36b00")
        self.log_text.tag_config("ERROR", foreground="#b00020")
        frm.rowconfigure(5, weight=1)

        ttk.Label(frm, text="Resultaten:").grid(row=6, column=0, sticky="nw", **pad)
        keys = [key for key, _ in RESULT_COLUMNS]
        self.tree = ttk.Treeview(frm, columns=keys, show="headings", height=5)
        for key, label in RESULT_COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=90 if key == "patch" else 140, anchor="center")
        self.tree.grid(row=7, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(frm, textvariable=self.output_var, foreground="#444444").grid(
            row=8, column=0, columnspan=4, sticky="w", **pad
        )

    def _browse(self):
        path = filedialog.askdirectory(title="Kies de CFD-case map")
        if path:
            self.case_var.set(path)

    def _append_log(self, line, level=None):
        self.log_text.configure(state="normal")
        tag = level if level in ("WARNING", "ERROR") else None
        self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start(self):
        case = self.case_var.get().strip()
        if not case or not os.path.isdir(case):
            messagebox.showerror("Geen case-map", "Kies eerst een geldige CFD-case map.")
            return

        # logvenster en resultatentabel leegmaken bij elke nieuwe start
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.output_var.set("")

        missing = missing_polymesh_files(case)
        if missing:
            msg = (
                f"In constant/polyMesh van deze case ontbreken: {', '.join(missing)}.\n"
                "Zet de case-map volledig lokaal beschikbaar (bijv. OneDrive: "
                "'Altijd op dit apparaat bewaren') of herstel de ontbrekende "
                "bestanden, en probeer het opnieuw."
            )
            self._append_log(
                "FOUT: mesh incompleet — ontbreekt in constant/polyMesh: "
                + ", ".join(missing),
                "ERROR",
            )
            messagebox.showerror("Mesh incompleet", msg)
            return
        try:
            kwargs = build_kwargs(
                case,
                self.slice_y_var.get(),
                self.slice_x_var.get(),
                self.overwrite_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Ongeldige invoer", str(exc))
            return

        self.start_btn.configure(state="disabled")
        self.status_var.set("Bezig met verwerken...")

        qh = _QueueHandler(self._log_queue)
        qh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
            )
        )

        def worker():
            try:
                result = case_runner.process_case(extra_handlers=[qh], **kwargs)
            except Exception as exc:  # wordt in het scherm gemeld
                self._log_queue.put(("ERR", exc))
            else:
                self._log_queue.put(("OK", result))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll)

    def _poll(self):
        while True:
            try:
                item = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, tuple):
                status, payload = item
                if status == "OK":
                    self._on_success(payload)
                else:
                    self._on_error(payload)
                return
            parts = item.split("|")
            level = parts[1].strip() if len(parts) > 1 else ""
            self._append_log(item, level if level in ("WARNING", "ERROR") else None)
        self.root.after(100, self._poll)

    def _on_success(self, result):
        self.start_btn.configure(state="normal")
        self.status_var.set("Klaar.")
        _, table = read_results_table(result["results_csv"])
        for row in table:
            self.tree.insert("", "end", values=row)
        pngs = result["slice_png"]
        n_slices = len(pngs) if isinstance(pngs, list) else (1 if pngs else 0)
        self.output_var.set(
            f"Output: {result['output_dir']} — results.csv, {n_slices} "
            "slice-figuur(en) en logbestand weggeschreven (figuren niet geopend)."
        )

    def _on_error(self, exc):
        self.start_btn.configure(state="normal")
        self.status_var.set("Verwerking mislukt.")
        if isinstance(exc, FileExistsError):
            self._append_log(
                f"FOUT: {exc} — vink 'overschrijven' aan om erin te schrijven.",
                "ERROR",
            )
            messagebox.showerror(
                "Output-map bestaat al",
                "output-custom bestaat al in de case-map.\n"
                "Vink 'Bestaande output-custom overschrijven' aan om erin te schrijven.",
            )
        elif isinstance(exc, FileNotFoundError):
            self._append_log(f"FOUT: {exc}", "ERROR")
            messagebox.showerror("Bestand ontbreekt", str(exc))
        else:
            self._append_log(f"FOUT: {exc} (details in het caselog)", "ERROR")


def main(argv=None) -> int:
    if tk is None:
        print(
            "FOUT: tkinter is niet beschikbaar in deze Python-installatie.",
            file=sys.stderr,
        )
        return 1
    root = tk.Tk()
    PostprocApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
