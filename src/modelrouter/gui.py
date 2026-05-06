"""Tkinter-based interactive playground for Modelrouter.

Launch from the command line::

    python -m modelrouter.gui

or from Python::

    from modelrouter.gui import launch_gui
    launch_gui()

Requires ``tkinter`` (part of the Python standard library; on some Linux
distributions install ``python3-tk`` via the system package manager).
"""

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
except ModuleNotFoundError as _err:  # pragma: no cover
    raise ModuleNotFoundError(
        "The modelrouter GUI requires tkinter. "
        "Install it with your system package manager, e.g. "
        "'sudo apt install python3-tk' on Debian/Ubuntu."
    ) from _err

from typing import Optional

from .router import Modelrouter

# ── Colour palette ────────────────────────────────────────────────────────────
_BG = "#f5f5f5"
_ACCENT = "#2563eb"       # blue-600
_ACCENT_FG = "#ffffff"
_PANEL_BG = "#ffffff"
_BORDER = "#d1d5db"
_MONO = ("Courier", 10)
_HEADING = ("TkDefaultFont", 11, "bold")


def launch_gui(router: Optional[Modelrouter] = None) -> None:
    """Open the interactive Modelrouter playground window.

    Parameters
    ----------
    router:
        A pre-configured :class:`~modelrouter.Modelrouter` instance to
        display. If omitted, a fresh router with ``default="gpt-4o-mini"``
        and a few example routes is created.
    """
    if router is None:
        router = _make_example_router()

    root = tk.Tk()
    root.title("Modelrouter Playground")
    root.geometry("960x640")
    root.minsize(760, 520)
    root.configure(bg=_BG)

    _App(root, router)
    root.mainloop()


# ── Example router pre-loaded for demo purposes ───────────────────────────────

def _make_example_router() -> Modelrouter:
    r = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
    r.add_route(
        "code",
        "gpt-4o",
        lambda p: any(kw in p.lower() for kw in ("code", "function", "script", "debug")),
        priority=10,
        cost_per_1k=0.005,
        tags=["prod"],
        condition_label="keyword:code|function|script|debug",
    )
    r.add_route(
        "long",
        "claude-opus-4-7",
        lambda p: len(p) > 1000,
        priority=5,
        cost_per_1k=0.015,
        tags=["prod", "expensive"],
        condition_label="len(prompt)>1000",
    )
    r.add_route(
        "translate",
        "gpt-4o-mini",
        lambda p: "translate" in p.lower(),
        priority=3,
        cost_per_1k=0.00015,
        tags=["prod"],
        condition_label="keyword:translate",
    )
    return r


# ── Main application ──────────────────────────────────────────────────────────

class _App:
    def __init__(self, root: tk.Tk, router: Modelrouter) -> None:
        self.root = root
        self.router = router
        self._build_ui()
        self._refresh_route_list()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_toolbar()

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = tk.Frame(paned, bg=_BG)
        right = tk.Frame(paned, bg=_BG)
        paned.add(left, weight=2)
        paned.add(right, weight=3)

        self._build_route_panel(left)
        self._build_right_panel(right)

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.root, bg=_ACCENT, padx=10, pady=6)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="Modelrouter Playground",
                 bg=_ACCENT, fg=_ACCENT_FG,
                 font=("TkDefaultFont", 13, "bold")).pack(side=tk.LEFT)

        # Default-model badge on the right
        tk.Label(bar, text="Default model:", bg=_ACCENT, fg=_ACCENT_FG).pack(side=tk.LEFT, padx=(30, 4))
        self.default_var = tk.StringVar(value=self.router.default)
        default_entry = tk.Entry(bar, textvariable=self.default_var, width=18,
                                 relief=tk.FLAT, bd=2)
        default_entry.pack(side=tk.LEFT)
        tk.Button(bar, text="Apply", command=self._apply_default,
                  bg="#1d4ed8", fg=_ACCENT_FG, relief=tk.FLAT,
                  padx=6).pack(side=tk.LEFT, padx=4)

    # ── Left panel: route list ─────────────────────────────────────────────────

    def _build_route_panel(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=_BG)
        header.pack(fill=tk.X, pady=(6, 2))
        tk.Label(header, text="Registered Routes", font=_HEADING,
                 bg=_BG).pack(side=tk.LEFT)
        tk.Button(header, text="Remove selected",
                  command=self._remove_selected,
                  bg="#ef4444", fg=_ACCENT_FG, relief=tk.FLAT, padx=6,
                  pady=2).pack(side=tk.RIGHT)

        frame = tk.Frame(parent, bg=_PANEL_BG, relief=tk.SOLID, bd=1)
        frame.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "model", "priority", "cost/1k", "tags", "condition")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                 selectmode="extended")
        widths = {"name": 90, "model": 130, "priority": 58,
                  "cost/1k": 58, "tags": 90, "condition": 160}
        for col in cols:
            self.tree.heading(col, text=col,
                              command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=widths[col], anchor="w",
                             minwidth=40)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # row-count label
        self.count_var = tk.StringVar(value="0 routes")
        tk.Label(parent, textvariable=self.count_var, bg=_BG,
                 fg="#6b7280", font=("TkDefaultFont", 9)).pack(anchor="w")

    # ── Right panel: add-route form + test panel ───────────────────────────────

    def _build_right_panel(self, parent: tk.Frame) -> None:
        self._build_add_form(parent)
        self._build_test_panel(parent)

    def _build_add_form(self, parent: tk.Frame) -> None:
        outer = tk.LabelFrame(parent, text="  Add Route  ",
                              bg=_PANEL_BG, relief=tk.SOLID, bd=1,
                              padx=10, pady=8)
        outer.pack(fill=tk.X, pady=(6, 6))

        fields = [
            ("Route name",      "name_var",     "my-route"),
            ("Target model",    "model_var",    "gpt-4o"),
            ("Keyword(s)",      "keyword_var",  "code, function"),
            ("Priority",        "priority_var", "0"),
            ("Cost /1k (USD)",  "cost_var",     "0.005"),
            ("Tags",            "tags_var",     "prod"),
        ]

        for row, (label, attr, placeholder) in enumerate(fields):
            tk.Label(outer, text=label, bg=_PANEL_BG,
                     anchor="w").grid(row=row, column=0, sticky="w",
                                      pady=3, padx=(0, 8))
            var = tk.StringVar(value=placeholder)
            setattr(self, attr, var)
            tk.Entry(outer, textvariable=var, relief=tk.SOLID,
                     bd=1, width=28).grid(row=row, column=1,
                                          sticky="ew", pady=3)

        outer.columnconfigure(1, weight=1)

        note = tk.Label(outer,
                        text="Keywords are comma-separated (case-insensitive OR match).",
                        bg=_PANEL_BG, fg="#6b7280",
                        font=("TkDefaultFont", 8))
        note.grid(row=len(fields), column=0, columnspan=2,
                  sticky="w", pady=(2, 4))

        tk.Button(outer, text="Add Route →",
                  command=self._add_route,
                  bg=_ACCENT, fg=_ACCENT_FG, relief=tk.FLAT,
                  padx=10, pady=4).grid(
            row=len(fields) + 1, column=0, columnspan=2, pady=(4, 2))

    def _build_test_panel(self, parent: tk.Frame) -> None:
        outer = tk.LabelFrame(parent, text="  Test Prompt  ",
                              bg=_PANEL_BG, relief=tk.SOLID, bd=1,
                              padx=10, pady=8)
        outer.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        tk.Label(outer, text="Prompt:", bg=_PANEL_BG).pack(anchor="w")
        self.prompt_text = scrolledtext.ScrolledText(
            outer, height=4, wrap=tk.WORD, relief=tk.SOLID, bd=1,
            font=_MONO)
        self.prompt_text.pack(fill=tk.X, pady=(2, 4))
        self.prompt_text.insert(tk.END, "Write a Python function to sort a list.")

        tk.Button(outer, text="Route this prompt →",
                  command=self._route_prompt,
                  bg=_ACCENT, fg=_ACCENT_FG, relief=tk.FLAT,
                  padx=10, pady=4).pack(pady=(0, 6))

        tk.Label(outer, text="Result:", bg=_PANEL_BG).pack(anchor="w")
        self.result_text = scrolledtext.ScrolledText(
            outer, height=9, wrap=tk.WORD, state=tk.DISABLED,
            relief=tk.SOLID, bd=1, font=_MONO,
            bg="#f8fafc")
        self.result_text.pack(fill=tk.BOTH, expand=True)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_route(self) -> None:
        name = self.name_var.get().strip()
        model = self.model_var.get().strip()
        keyword_raw = self.keyword_var.get().strip()
        keywords = [k.strip().lower() for k in keyword_raw.split(",") if k.strip()]

        try:
            priority = int(self.priority_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Priority must be an integer.")
            return

        try:
            cost = float(self.cost_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Cost must be a decimal number.")
            return

        tags = [t.strip() for t in self.tags_var.get().split(",") if t.strip()]

        if not name or not model or not keywords:
            messagebox.showerror("Missing fields",
                                 "Route name, target model, and at least one keyword are required.")
            return

        condition = lambda p, kws=keywords: any(kw in p.lower() for kw in kws)
        label = "keyword:" + "|".join(keywords)

        try:
            self.router.add_route(
                name=name, model=model, condition=condition,
                priority=priority, cost_per_1k=cost,
                tags=tags, condition_label=label,
            )
        except ValueError as exc:
            messagebox.showerror("Route error", str(exc))
            return

        self._refresh_route_list()
        self._set_result(f"Route {name!r} added successfully.")

    def _remove_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Select one or more routes in the list first.")
            return
        names = [self.tree.item(item, "values")[0] for item in selected]
        for name in names:
            self.router.remove_route(name)
        self._refresh_route_list()
        self._set_result(f"Removed route(s): {', '.join(names)}")

    def _route_prompt(self) -> None:
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo("Empty prompt", "Enter a prompt to test routing.")
            return

        exp = self.router.explain(prompt)
        model, cost = self.router.resolve_with_cost(prompt)

        divider = "─" * 44
        lines = [
            f"Prompt length  : {len(prompt)} characters",
            divider,
            f"Model selected : {exp['model']}",
            f"Route matched  : {exp['reason']}",
            f"Priority       : {exp['priority']}",
            f"Cost /1k tokens: ${cost:.5f}",
            f"Tags           : {', '.join(exp['tags']) or '—'}",
            f"Condition      : {exp['condition_label'] or '—'}",
            divider,
            f"explain() dict :",
        ]
        for k, v in exp.items():
            lines.append(f"  {k:<18}: {v!r}")
        self._set_result("\n".join(lines))

    def _apply_default(self) -> None:
        new_default = self.default_var.get().strip()
        if not new_default:
            messagebox.showerror("Invalid", "Default model name cannot be empty.")
            return
        if new_default == self.router.default:
            return
        old_routes = self.router.routes()
        self.router = Modelrouter(
            default=new_default,
            default_cost_per_1k=self.router.default_cost,
        )
        for r in old_routes:
            self.router.add_route(
                r.name, r.model, r.condition,
                r.priority, r.cost_per_1k, r.tags, r.condition_label,
            )
        self._refresh_route_list()
        self._set_result(f"Default model updated to {new_default!r}.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_route_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self.router.routes():
            self.tree.insert("", tk.END, values=(
                r.name,
                r.model,
                r.priority,
                f"{r.cost_per_1k:.5f}",
                ", ".join(r.tags) or "—",
                r.condition_label or "—",
            ))
        count = len(self.router)
        self.count_var.set(f"{count} route{'s' if count != 1 else ''}")

    def _sort_tree(self, col: str) -> None:
        """Toggle ascending/descending sort on the treeview column."""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda t: float(t[0]))
        except ValueError:
            items.sort(key=lambda t: t[0].lower())
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _set_result(self, text: str) -> None:
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.config(state=tk.DISABLED)


# ── Module entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover
    launch_gui()
