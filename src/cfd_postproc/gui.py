"""Interactief startscherm voor cfd_postproc.

Dunne tkinter-schil boven case_runner.process_case(): de gebruiker kiest een
CFD-case map, start de postprocessing en ziet live de log plus na afloop de
resultaten (weerstand, frontaal oppervlak, CD, CdA) in een tabel. Figuren en
het logbestand worden weggeschreven naar output-custom in de case-map, maar
niet geopend.

Starten: dubbelklik start.bat in de repo-root, of:

    python -m src.cfd_postproc.gui
"""

from __future__ import annotations

import csv
import logging
import os
import queue
import sys
import threading

import numpy as np

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:  # tkinter zit standaard in Python op Windows
    tk = None

from . import case_runner, geometrie, of_io
from .__main__ import DEFAULT_SLICE_X

# atleetpatches waarvoor de geometrie wordt getoond (zelfde default als process_case)
BODY_PATCHES: tuple[str, ...] = ("pilot", "stoker")

# warn-meldingen bij het terugvallen van de geometrie op de polyMesh
_WARN_STL_PATCHEN = (
    "STL-geometrie niet bruikbaar voor patches {patches}; val terug op de "
    "polyMesh (kan lang duren bij grote cases)."
)
_WARN_GEEN_STL = (
    "Geen STL-geometrie gevonden (constant/triSurface of bijbehorende "
    "Mesh_-map); polyMesh wordt gelezen (kan lang duren bij grote cases)."
)


def compute_geometry_payload(case_dir, body_patches=BODY_PATCHES):
    """Bereken het geometrie-payload voor een case (display-vrij).

    Voorkeursroute: STL's via read_body_triangles; fallback: polyMesh.
    Retourneert (payload, waarschuwingen), waar payload het tuple is dat
    _open_geometry_window verwacht:
    (views, polys3d, bmin, bmax, n_total, n_3d, s, bron, kleuren3d).
    Bij de STL-route zijn de views dict {patchnaam: mask} en kleuren3d een
    lijst met één kleur per 3D-polygoon; bij de polyMesh-fallback een enkel
    mask en None (alles in één kleur, zoals voorheen).
    """
    warns: list[str] = []
    tris_map = geometrie.read_body_triangles(case_dir, body_patches)
    if tris_map is not None:
        all_tris = np.concatenate(list(tris_map.values()))
        bmin, bmax = geometrie.bounding_box_triangles(all_tris)
        # 2D: per atleet rasteriseren op hetzelfde rooster, zodat pilot en
        # stoker elk hun eigen kleur kunnen krijgen
        views = {}
        for v in ("front", "side", "top"):
            a, b = geometrie.VIEWS[v][0]
            ext = (float(bmin[a]), float(bmax[a]), float(bmin[b]), float(bmax[b]))
            bodies = {
                naam: geometrie.raster_view_triangles(tris_map[naam], v, extent=ext)[0]
                for naam in tris_map
            }
            views[v] = (bodies, ext)
        # 3D: decimatie per atleet, budget naar rato van het aantal driehoeken
        # zodat het totaal ≤ DEFAULT_MAX_POLYS_3D blijft; pilot wordt als
        # laatste getekend (bovenop)
        volgorde = [n for n in geometrie._PATCH_ORDER if n in tris_map] + sorted(
            set(tris_map) - set(geometrie._PATCH_ORDER)
        )
        n_all = max(len(all_tris), 1)
        polys3d: list = []
        kleuren: list = []
        s = 1.0
        for naam in volgorde:
            budget = max(
                1, int(geometrie.DEFAULT_MAX_POLYS_3D * len(tris_map[naam]) / n_all)
            )
            sel, _h, s_body = geometrie.decimate_triangles(tris_map[naam], budget)
            polys3d.extend(geometrie.inflate_polygons(list(sel), s_body))
            kleuren.extend(
                [geometrie.PATCH_COLORS.get(naam, "#08306b")] * len(sel)
            )
            s = max(s, s_body)
        payload = (
            views, polys3d, bmin, bmax, len(all_tris), len(polys3d), s, "stl",
            kleuren,
        )
        return payload, warns
    if geometrie.find_stl_dir(case_dir) is not None:
        warns.append(_WARN_STL_PATCHEN.format(patches=body_patches))
    else:
        warns.append(_WARN_GEEN_STL)
    mesh = of_io.read_mesh(case_dir)
    ids = geometrie.body_face_ids(mesh, body_patches)
    bmin, bmax = geometrie.bounding_box(mesh, ids)
    views = {
        v: geometrie.raster_view(mesh, ids, v)
        for v in ("front", "side", "top")
    }
    ids3d, h = geometrie.decimate_surface(
        mesh, ids, geometrie.DEFAULT_MAX_POLYS_3D
    )
    s = geometrie.inflation_factor(mesh, ids, h)
    polys3d = geometrie.inflate_polygons(
        geometrie.polygons_of(mesh, ids3d), s
    )
    payload = (
        views, polys3d, bmin, bmax, len(ids), len(ids3d), s, "polymesh", None
    )
    return payload, warns

# Kolommen van results.csv die in het scherm getoond worden: (csv-sleutel, titel)
RESULT_COLUMNS = [
    ("patch", "patch"),
    ("weerstand_N", "weerstand [N]"),
    ("aandeel_van_totaal_pct", "aandeel [%]"),
    ("frontaal_oppervlak_m2", "frontaal oppervlak [m²]"),
    ("CD", "CD"),
    ("CdA_m2", "CdA [m²]"),
]


# polyMesh-bestanden die aanwezig moeten zijn vóór een run start
POLYMESH_FILES = ("points", "faces", "owner", "neighbour", "boundary")

# Vaste notitie in het startscherm bij de slice-velden
SLICE_NOTE = (
    "Slice-figuren worden weggeschreven naar output-custom in de case-map "
    "(worden niet geopend).\n"
    "De manier waarop slices worden gemaakt wordt in een volgende versie "
    "verbeterd (zie plan-van-aanpak.md §12, punt 7)."
)


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
        self._geo_queue = queue.Queue()
        self._geo_cache = {}  # case -> geometrie-payload (zelfde sessie)
        self._views_queue = queue.Queue()
        self._views_token = 0  # verlopen resultaten van oudere selecties negeren
        self._views_polling = False
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
        ttk.Label(
            frm,
            text="Slice-invoer: komma-gescheiden posities in meter, bijv. 0.0 of -1.0,0.0,0.5",
            foreground="#666666",
        ).grid(row=2, column=0, columnspan=4, sticky="w", **pad)
        ttk.Label(
            frm,
            text=SLICE_NOTE,
            foreground="#666666",
            justify="left",
        ).grid(row=3, column=0, columnspan=4, sticky="w", **pad)

        ttk.Checkbutton(
            frm,
            text="Bestaande output-custom overschrijven",
            variable=self.overwrite_var,
        ).grid(row=4, column=0, columnspan=4, sticky="w", **pad)

        self.start_btn = ttk.Button(
            frm, text="Start postprocessing", command=self._start
        )
        self.start_btn.grid(row=5, column=0, sticky="w", pady=(6, 2))
        self.geo_btn = ttk.Button(
            frm, text="Geometrie tonen", command=self._show_geometry
        )
        self.geo_btn.grid(row=5, column=1, sticky="w", pady=(6, 2))
        ttk.Label(frm, textvariable=self.status_var).grid(
            row=5, column=2, columnspan=2, sticky="w", **pad
        )

        ttk.Label(frm, text="Log:").grid(row=6, column=0, sticky="nw", **pad)
        self.log_text = scrolledtext.ScrolledText(
            frm, height=10, width=90, state="disabled"
        )
        self.log_text.grid(row=7, column=0, columnspan=4, sticky="nsew", **pad)
        self.log_text.tag_config("WARNING", foreground="#b36b00")
        self.log_text.tag_config("ERROR", foreground="#b00020")
        frm.rowconfigure(7, weight=1)

        # 2D-aanzichten, standaard zichtbaar tussen log en resultaten
        ttk.Label(frm, text="Aanzichten:").grid(row=8, column=0, sticky="nw", **pad)
        views_frm = ttk.Frame(frm)
        views_frm.grid(row=8, column=1, columnspan=3, sticky="ew", **pad)
        self._views_placeholder = ttk.Label(
            views_frm,
            text="(aanzichten verschijnen na het kiezen van een case-map)",
            foreground="#999999",
        )
        self._views_placeholder.pack(anchor="w", padx=2, pady=2)
        self._view_frames = {}
        for _view, _naam in (
            ("front", "Vooraanzicht"),
            ("side", "Zijaanzicht"),
            ("top", "Bovenaanzicht"),
        ):
            lf = ttk.LabelFrame(views_frm, text=_naam)
            # tussenrapport: pas zichtbaar na het laden (zie _draw_view_panels)
            lf.pack_forget()
            self._view_frames[_view] = lf

        ttk.Label(frm, text="Resultaten:").grid(row=9, column=0, sticky="nw", **pad)
        keys = [key for key, _ in RESULT_COLUMNS]
        self.tree = ttk.Treeview(frm, columns=keys, show="headings", height=5)
        for key, label in RESULT_COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=90 if key == "patch" else 140, anchor="center")
        self.tree.grid(row=10, column=0, columnspan=4, sticky="ew", **pad)

        ttk.Label(frm, textvariable=self.output_var, foreground="#444444").grid(
            row=11, column=0, columnspan=4, sticky="w", **pad
        )

    def _browse(self):
        path = filedialog.askdirectory(title="Kies de CFD-case map")
        if path:
            self.case_var.set(path)
            self._load_views_for_case()

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

    def _load_views_for_case(self):
        """Laad de 2D-aanzichten voor de gekozen case in een achtergrondthread.

        Zelfde berekening als 'Geometrie tonen' (gedeeld via
        compute_geometry_payload); het resultaat komt terecht in de
        ingebedde panels tussen log en resultaten én in de sessie-cache.
        """
        case = self.case_var.get().strip()
        if not case or not os.path.isdir(case):
            return
        # cache-hit: direct tekenen, geen thread nodig
        if case in self._geo_cache:
            self._draw_view_panels(self._geo_cache[case][0])
            return
        self._views_token += 1
        token = self._views_token
        self._views_placeholder.configure(
            text="aanzichten laden...", foreground="#999999"
        )
        self._views_placeholder.pack(anchor="w", padx=2, pady=2)
        self.status_var.set("Aanzichten laden...")

        def worker():
            try:
                payload, warns = compute_geometry_payload(case, BODY_PATCHES)
                self._views_queue.put(("VIEW_OK", token, payload, warns))
            except Exception as exc:
                self._views_queue.put(("VIEW_ERR", token, case, exc))

        threading.Thread(target=worker, daemon=True).start()
        if not self._views_polling:
            self._views_polling = True
            self.root.after(100, self._poll_views)

    def _poll_views(self):
        try:
            msg = self._views_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_views)
            return
        if msg[0] == "VIEW_OK":
            _status, token, payload, warns = msg
            if token != self._views_token:
                self.root.after(100, self._poll_views)
                return
            case = self.case_var.get().strip()
            self._geo_cache[case] = payload
            for w in warns:
                self._append_log(f"WAARSCHUWING: {w}", "WARNING")
            self._draw_view_panels(payload[0])
            bron = "STL" if payload[7] == "stl" else "polyMesh"
            self.status_var.set(
                f"Aanzichten geladen ({bron}); draaibaar 3D via 'Geometrie tonen'."
            )
        elif msg[0] == "VIEW_ERR":
            _status, token, case, exc = msg
            self.status_var.set("Aanzichten laden mislukt.")
            self._append_log(f"FOUT: aanzichten laden: {exc}", "ERROR")
        self.root.after(100, self._poll_views)

    def _draw_view_panels(self, views):
        """Teken de drie 2D-aanzichten klein, ingebed tussen log en resultaten."""
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self._views_placeholder.pack_forget()
        for view, _naam in (
            ("front", "Vooraanzicht"),
            ("side", "Zijaanzicht"),
            ("top", "Bovenaanzicht"),
        ):
            lf = self._view_frames[view]
            for w in lf.winfo_children():
                w.destroy()
            mask, extent = views[view]
            fig = geometrie.make_view_figure(
                view, mask, extent, figsize=(3.1, 2.5), with_title=False
            )
            canvas = FigureCanvasTkAgg(fig, master=lf)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            canvas.draw()
            lf.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=2)
        self.root.update_idletasks()

    def _show_geometry(self):
        """Laad de geometrie in een achtergrondthread en open het venster.

        Voorkeur: STL's van de atleten (snel, geen polyMesh nodig); anders de
        body-patches uit de polyMesh (fallback).
        """
        case = self.case_var.get().strip()
        if not case or not os.path.isdir(case):
            messagebox.showerror("Geen case-map", "Kies eerst een geldige CFD-case map.")
            return
        # zelfde sessie + zelfde case: direct openen uit de cache
        if case in self._geo_cache:
            payload = self._geo_cache[case]
            self.status_var.set("Geometrie uit cache geladen.")
            self._open_geometry_window(*payload)
            return
        stl_mode = geometrie.find_stl_dir(case) is not None
        if not stl_mode:
            missing = missing_polymesh_files(case)
            if missing:
                messagebox.showerror(
                    "Mesh incompleet",
                    f"In constant/polyMesh ontbreken: {', '.join(missing)}.",
                )
                return

        self.geo_btn.configure(state="disabled")
        self.status_var.set(
            "Geometrie laden uit STL..." if stl_mode else "Mesh laden voor geometrie..."
        )

        def worker():
            try:
                payload, warns = compute_geometry_payload(case, BODY_PATCHES)
                for w in warns:
                    self._geo_queue.put(("WARN", w))
                self._geo_queue.put(("OK", payload))
            except Exception as exc:  # wordt in het scherm gemeld
                self._geo_queue.put(("ERR", exc))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._poll_geo)

    def _poll_geo(self):
        try:
            status, payload = self._geo_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_geo)
            return
        if status == "WARN":
            self._append_log(f"WAARSCHUWING: {payload}", "WARNING")
            self.root.after(100, self._poll_geo)
            return
        self.geo_btn.configure(state="normal")
        if status == "ERR":
            self.status_var.set("Geometrie laden mislukt.")
            self._append_log(f"FOUT: geometrie laden: {payload}", "ERROR")
            messagebox.showerror("Geometrie laden mislukt", str(payload))
            return
        views, polys3d, bmin, bmax, n_total, n_3d, s, source, kleuren = payload
        self._geo_cache[self.case_var.get().strip()] = payload
        if source == "stl":
            self.status_var.set(f"Geometrie geladen uit STL ({n_total} driehoeken).")
        else:
            self.status_var.set(f"Geometrie geladen ({n_total} body-faces).")
        self._open_geometry_window(
            views, polys3d, bmin, bmax, n_total, n_3d, s, source, kleuren
        )

    def _open_geometry_window(
        self, views, polys3d, bmin, bmax, n_total, n_3d, s, source, kleuren=None
    ):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        case = self.case_var.get().strip().rstrip("\\/")
        win = tk.Toplevel(self.root)
        win.title(f"Geometrie — {os.path.basename(case)}")
        win.minsize(720, 580)

        if source == "stl":
            detail = (
                f"({n_total} driehoeken uit STL; 2D solid via raster; "
                f"3D: {n_3d} polygonen, decimatie + inflatie ×{s:.1f} = solid)"
            )
        else:
            detail = (
                f"({n_total} faces; 2D solid via raster; 3D: {n_3d} polygonen, "
                f"cel-decimatie + inflatie ×{s:.1f} = solid)"
            )
        ttk.Label(
            win,
            text=(
                f"Atleetpatches {BODY_PATCHES} — {geometrie.sizes_text(bmin, bmax)} "
                f"{detail}"
            ),
        ).pack(padx=8, pady=(8, 0), anchor="w")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for view, naam in (
            ("front", "Vooraanzicht"),
            ("side", "Zijaanzicht"),
            ("top", "Bovenaanzicht"),
        ):
            tab = ttk.Frame(nb)
            nb.add(tab, text=naam)
            mask, extent = views[view]
            fig = geometrie.make_view_figure(view, mask, extent)
            FigureCanvasTkAgg(fig, master=tab).get_tk_widget().pack(
                fill="both", expand=True
            )

        tab3d = ttk.Frame(nb)
        nb.add(tab3d, text="3D (draaien)")
        ttk.Label(
            tab3d,
            text="Sleep met de muis over de figuur om te draaien; scroll om te zoomen.",
        ).pack(anchor="w", padx=4, pady=2)
        fig3d = geometrie.make_3d_figure(polys3d, bmin, bmax, kleuren=kleuren)
        FigureCanvasTkAgg(fig3d, master=tab3d).get_tk_widget().pack(
            fill="both", expand=True
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
