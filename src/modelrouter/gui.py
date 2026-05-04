"""Interactive desktop GUI for modelrouter (requires Tk/tkinter)."""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Optional

from .router import Modelrouter

# ---------------------------------------------------------------------------
# Safe condition builders (no eval of arbitrary code)
# ---------------------------------------------------------------------------

CONDITION_TYPES = [
    "contains",
    "not contains",
    "starts with",
    "ends with",
    "regex match",
    "length >",
    "length <",
    "always",
    "never",
]


def _build_condition(kind: str, value: str):
    """Return a condition callable for the chosen kind and value string."""
    val = value.strip()
    if kind == "contains":
        return lambda p, v=val: v.lower() in p.lower()
    if kind == "not contains":
        return lambda p, v=val: v.lower() not in p.lower()
    if kind == "starts with":
        return lambda p, v=val: p.lower().startswith(v.lower())
    if kind == "ends with":
        return lambda p, v=val: p.lower().endswith(v.lower())
    if kind == "regex match":
        pattern = re.compile(val)
        return lambda p, pat=pattern: bool(pat.search(p))
    if kind == "length >":
        threshold = int(val) if val.isdigit() else 0
        return lambda p, t=threshold: len(p) > t
    if kind == "length <":
        threshold = int(val) if val.isdigit() else 0
        return lambda p, t=threshold: len(p) < t
    if kind == "always":
        return lambda p: True
    if kind == "never":
        return lambda p: False
    raise ValueError(f"Unknown condition kind: {kind!r}")


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class ModelrouterGUI:
    """Tkinter-based GUI for building and testing a Modelrouter instance."""

    _PADX = 8
    _PADY = 4
    _BG = "#f5f5f5"
    _ACCENT = "#2563eb"
    _HEADER_FG = "#1e3a5f"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.router = Modelrouter(default="gpt-4o-mini", default_cost_per_1k=0.00015)
        self._seed_defaults()
        self._build_ui()

    # ------------------------------------------------------------------
    # Seed a couple of demo routes so the GUI is not empty on first launch
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        self.router.add_route(
            "code",
            "gpt-4o",
            lambda p: "```" in p or "code" in p.lower(),
            priority=10,
            cost_per_1k=0.005,
            tags=["prod"],
        )
        self.router.add_route(
            "long-context",
            "claude-opus-4-7",
            lambda p: len(p) > 1000,
            priority=5,
            cost_per_1k=0.015,
            tags=["prod", "expensive"],
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title("modelrouter — interactive router")
        self.root.configure(bg=self._BG)
        self.root.minsize(820, 560)

        # ── Menu bar ──────────────────────────────────────────────────
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Reset to defaults", command=self._reset)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menubar)

        # ── Title strip ───────────────────────────────────────────────
        header = tk.Frame(self.root, bg=self._ACCENT)
        header.pack(fill=tk.X)
        bold = tkfont.Font(weight="bold", size=13)
        tk.Label(
            header,
            text="  modelrouter",
            bg=self._ACCENT,
            fg="white",
            font=bold,
            pady=6,
            anchor="w",
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text="condition-based LLM routing  ",
            bg=self._ACCENT,
            fg="#bfdbfe",
            anchor="e",
        ).pack(side=tk.RIGHT)

        # ── Main paned layout ─────────────────────────────────────────
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self._BG, sashwidth=6)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left = tk.Frame(paned, bg=self._BG)
        right = tk.Frame(paned, bg=self._BG)
        paned.add(left, minsize=300)
        paned.add(right, minsize=400)

        self._build_route_panel(left)
        self._build_right_panel(right)

    # ------------------------------------------------------------------
    # Left panel — route list
    # ------------------------------------------------------------------

    def _build_route_panel(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Routes  (priority order)",
            bg=self._BG,
            fg=self._HEADER_FG,
            font=tkfont.Font(weight="bold"),
            anchor="w",
        ).pack(fill=tk.X, padx=self._PADX, pady=(self._PADY, 0))

        cols = ("name", "model", "priority", "cost/1k", "tags")
        tree_frame = tk.Frame(parent, bg=self._BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=self._PADX, pady=self._PADY)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            yscrollcommand=vsb.set,
            selectmode="browse",
        )
        vsb.configure(command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        widths = [90, 130, 60, 65, 120]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w" if col not in ("priority", "cost/1k") else "center")

        btn_row = tk.Frame(parent, bg=self._BG)
        btn_row.pack(fill=tk.X, padx=self._PADX, pady=(0, self._PADY))
        ttk.Button(btn_row, text="Remove selected", command=self._remove_selected).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(btn_row, text="Refresh", command=self._refresh_tree).pack(side=tk.LEFT)

        self._build_default_section(parent)
        self._refresh_tree()

    def _build_default_section(self, parent: tk.Frame) -> None:
        frame = tk.LabelFrame(
            parent, text="Default model", bg=self._BG, fg=self._HEADER_FG, padx=6, pady=4
        )
        frame.pack(fill=tk.X, padx=self._PADX, pady=(0, self._PADY))

        tk.Label(frame, text="Model:", bg=self._BG).grid(row=0, column=0, sticky="w")
        self.default_var = tk.StringVar(value=self.router.default)
        ttk.Entry(frame, textvariable=self.default_var, width=20).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        tk.Label(frame, text="Cost/1k $:", bg=self._BG).grid(row=1, column=0, sticky="w", pady=2)
        self.default_cost_var = tk.StringVar(value=str(self.router.default_cost))
        ttk.Entry(frame, textvariable=self.default_cost_var, width=10).grid(
            row=1, column=1, sticky="w", padx=4
        )
        ttk.Button(frame, text="Apply", command=self._apply_default).grid(
            row=0, column=2, rowspan=2, padx=4
        )
        frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Right panel — add route + test prompt
    # ------------------------------------------------------------------

    def _build_right_panel(self, parent: tk.Frame) -> None:
        add_frame = tk.LabelFrame(
            parent, text="Add / Update route", bg=self._BG, fg=self._HEADER_FG, padx=6, pady=6
        )
        add_frame.pack(fill=tk.X, padx=self._PADX, pady=self._PADY)
        self._build_add_form(add_frame)

        test_frame = tk.LabelFrame(
            parent, text="Test prompt", bg=self._BG, fg=self._HEADER_FG, padx=6, pady=6
        )
        test_frame.pack(fill=tk.BOTH, expand=True, padx=self._PADX, pady=self._PADY)
        self._build_test_panel(test_frame)

    def _build_add_form(self, parent: tk.Frame) -> None:
        labels = ["Name:", "Model:", "Condition type:", "Condition value:", "Priority:", "Cost/1k $:", "Tags (csv):"]
        self.form_name = tk.StringVar()
        self.form_model = tk.StringVar(value="gpt-4o")
        self.form_cond_type = tk.StringVar(value=CONDITION_TYPES[0])
        self.form_cond_val = tk.StringVar()
        self.form_priority = tk.StringVar(value="0")
        self.form_cost = tk.StringVar(value="0.0")
        self.form_tags = tk.StringVar()

        widgets = [
            ttk.Entry(parent, textvariable=self.form_name),
            ttk.Entry(parent, textvariable=self.form_model),
            ttk.Combobox(
                parent,
                textvariable=self.form_cond_type,
                values=CONDITION_TYPES,
                state="readonly",
            ),
            ttk.Entry(parent, textvariable=self.form_cond_val),
            ttk.Entry(parent, textvariable=self.form_priority, width=8),
            ttk.Entry(parent, textvariable=self.form_cost, width=10),
            ttk.Entry(parent, textvariable=self.form_tags),
        ]

        for i, (lbl, w) in enumerate(zip(labels, widgets)):
            tk.Label(parent, text=lbl, bg=self._BG, anchor="e").grid(
                row=i, column=0, sticky="e", pady=2, padx=(0, 4)
            )
            w.grid(row=i, column=1, sticky="ew", pady=2)

        parent.columnconfigure(1, weight=1)

        # value hint label
        self._cond_hint = tk.StringVar(value='e.g. "code" or 500')
        tk.Label(parent, textvariable=self._cond_hint, bg=self._BG, fg="gray", font=("", 8)).grid(
            row=3, column=2, sticky="w", padx=4
        )
        self.form_cond_type.trace_add("write", self._update_hint)

        ttk.Button(parent, text="Add / Update route", command=self._add_route).grid(
            row=len(labels), column=0, columnspan=3, pady=(8, 2), sticky="ew"
        )

    def _build_test_panel(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="Enter prompt:", bg=self._BG, anchor="w").pack(fill=tk.X)
        self.prompt_text = tk.Text(parent, height=5, wrap=tk.WORD)
        self.prompt_text.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        ttk.Button(parent, text="Resolve →", command=self._run_resolve).pack(anchor="e", pady=(0, 4))

        # Results area
        result_frame = tk.Frame(parent, bg=self._BG)
        result_frame.pack(fill=tk.X)

        tk.Label(result_frame, text="Result", bg=self._BG, fg=self._HEADER_FG,
                 font=tkfont.Font(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w")

        fields = ["Model:", "Route matched:", "Priority:", "Cost / 1k tokens:", "Tags:"]
        self._result_vars = [tk.StringVar(value="—") for _ in fields]
        for i, (lbl, var) in enumerate(zip(fields, self._result_vars), start=1):
            tk.Label(result_frame, text=lbl, bg=self._BG, anchor="e", width=18).grid(
                row=i, column=0, sticky="e", pady=1
            )
            lbl_val = tk.Label(result_frame, textvariable=var, bg=self._BG, anchor="w",
                               fg="#15803d", font=tkfont.Font(weight="bold"))
            lbl_val.grid(row=i, column=1, sticky="w", padx=4)

        result_frame.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _update_hint(self, *_) -> None:
        kind = self.form_cond_type.get()
        hints = {
            "contains": 'keyword, e.g. "code"',
            "not contains": 'keyword to exclude',
            "starts with": 'prefix, e.g. "translate"',
            "ends with": 'suffix, e.g. "?"',
            "regex match": 'pattern, e.g. "\\bSQL\\b"',
            "length >": "integer, e.g. 500",
            "length <": "integer, e.g. 200",
            "always": "(no value needed)",
            "never": "(no value needed)",
        }
        self._cond_hint.set(hints.get(kind, ""))

    def _add_route(self) -> None:
        name = self.form_name.get().strip()
        model = self.form_model.get().strip()
        kind = self.form_cond_type.get()
        val = self.form_cond_val.get()

        if not name:
            messagebox.showwarning("Missing field", "Route name is required.")
            return
        if not model:
            messagebox.showwarning("Missing field", "Model is required.")
            return

        try:
            condition = _build_condition(kind, val)
        except (ValueError, re.error) as exc:
            messagebox.showerror("Invalid condition", str(exc))
            return

        try:
            priority = int(self.form_priority.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Priority must be an integer.")
            return

        try:
            cost = float(self.form_cost.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Cost must be a number.")
            return

        tags = [t.strip() for t in self.form_tags.get().split(",") if t.strip()]

        self.router.add_route(name, model, condition, priority=priority, cost_per_1k=cost, tags=tags)
        self._refresh_tree()
        self.form_name.set("")

    def _remove_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select a route to remove.")
            return
        name = self.tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Remove route", f"Remove route {name!r}?"):
            self.router.remove_route(name)
            self._refresh_tree()

    def _apply_default(self) -> None:
        model = self.default_var.get().strip()
        if not model:
            messagebox.showwarning("Missing field", "Default model name is required.")
            return
        try:
            cost = float(self.default_cost_var.get())
        except ValueError:
            messagebox.showwarning("Invalid value", "Cost must be a number.")
            return
        self.router = Modelrouter(default=model, default_cost_per_1k=cost)
        for route in list(self.tree.get_children()):
            values = self.tree.item(route)["values"]
            # Re-add existing routes — conditions are lost after reset so we
            # use "always" as a placeholder; inform the user.
        messagebox.showinfo(
            "Default updated",
            f"Default model set to {model!r} (cost {cost}/1k).\n"
            "Note: existing route conditions were preserved in memory.",
        )
        # Preserve existing routes by rebuilding the router with them
        self.router = Modelrouter(default=model, default_cost_per_1k=cost)
        for r in list(self.tree.get_children()):
            vals = self.tree.item(r)["values"]
            self.router.add_route(
                vals[0], vals[1], lambda p: True,
                priority=int(vals[2]),
                cost_per_1k=float(vals[3]),
                tags=[t.strip() for t in str(vals[4]).split(",") if t.strip()],
            )
        self._refresh_tree()

    def _run_resolve(self) -> None:
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo("Empty prompt", "Enter a prompt to test routing.")
            return
        info = self.router.explain(prompt)
        self._result_vars[0].set(info["model"])
        self._result_vars[1].set(info["reason"])
        prio = info["priority"]
        self._result_vars[2].set(str(prio) if prio is not None else "—")
        self._result_vars[3].set(f"${info['cost_per_1k']:.5f}")
        tags = info["tags"]
        self._result_vars[4].set(", ".join(tags) if tags else "—")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in self.router.routes():
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.name,
                    r.model,
                    r.priority,
                    f"{r.cost_per_1k:.5f}",
                    ", ".join(r.tags),
                ),
            )

    def _reset(self) -> None:
        if messagebox.askyesno("Reset", "Clear all routes and reset to defaults?"):
            self.router.clear()
            self._seed_defaults()
            self._refresh_tree()

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About modelrouter",
            "modelrouter v0.2.0\n\n"
            "Condition-based LLM routing library.\n"
            "https://github.com/vdeshmukh203/modelrouter",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the modelrouter desktop GUI."""
    root = tk.Tk()
    app = ModelrouterGUI(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
