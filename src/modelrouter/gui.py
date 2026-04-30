"""Interactive Tkinter GUI for configuring and testing modelrouter.

Launch with::

    python -m modelrouter.gui

or, after installation::

    modelrouter-gui
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Callable, Optional

from .router import Modelrouter, Route

# ---------------------------------------------------------------------------
# Condition builders
# ---------------------------------------------------------------------------

_CONDITION_TYPES = [
    "contains",
    "starts with",
    "ends with",
    "length >",
    "length <",
    "regex",
    "custom expression",
]


def _build_condition(
    ctype: str, value: str
) -> Callable[[str], bool]:
    """Return a condition callable from a type + value pair.

    Raises
    ------
    ValueError
        If *value* is empty or produces an invalid expression.
    """
    v = value.strip()
    if ctype in ("contains", "starts with", "ends with", "regex") and not v:
        raise ValueError("Value must not be empty.")
    if ctype == "contains":
        return lambda p, _v=v: _v in p
    if ctype == "starts with":
        return lambda p, _v=v: p.startswith(_v)
    if ctype == "ends with":
        return lambda p, _v=v: p.endswith(_v)
    if ctype == "length >":
        try:
            n = int(v)
        except ValueError:
            raise ValueError(f"Expected an integer for length, got {v!r}.")
        return lambda p, _n=n: len(p) > _n
    if ctype == "length <":
        try:
            n = int(v)
        except ValueError:
            raise ValueError(f"Expected an integer for length, got {v!r}.")
        return lambda p, _n=n: len(p) < _n
    if ctype == "regex":
        try:
            pattern = re.compile(v)
        except re.error as exc:
            raise ValueError(f"Invalid regex: {exc}") from exc
        return lambda p, _pat=pattern: bool(_pat.search(p))
    if ctype == "custom expression":
        if not v:
            raise ValueError("Custom expression must not be empty.")
        try:
            # Validate the expression compiles before storing it.
            compiled = compile(v, "<condition>", "eval")
        except SyntaxError as exc:
            raise ValueError(f"Syntax error in expression: {exc}") from exc

        def _custom(p: str, _c=compiled) -> bool:
            return bool(eval(_c, {"__builtins__": {}}, {"p": p}))  # noqa: S307

        return _custom
    raise ValueError(f"Unknown condition type: {ctype!r}")


# ---------------------------------------------------------------------------
# Add-route dialog
# ---------------------------------------------------------------------------

class _AddRouteDialog(tk.Toplevel):
    """Modal dialog for adding a new route."""

    def __init__(self, parent: tk.Widget, router: Modelrouter) -> None:
        super().__init__(parent)
        self.title("Add Route")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._router = router
        self.result: Optional[Route] = None
        self._build()
        self.wait_window()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self, padding=12)
        frame.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)

        def _lbl(row: int, text: str) -> None:
            ttk.Label(frame, text=text).grid(row=row, column=0, sticky="w", **pad)

        _lbl(0, "Name:")
        self._name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._name_var, width=30).grid(
            row=0, column=1, sticky="ew", **pad
        )

        _lbl(1, "Model:")
        self._model_var = tk.StringVar(value="gpt-4o")
        ttk.Entry(frame, textvariable=self._model_var, width=30).grid(
            row=1, column=1, sticky="ew", **pad
        )

        _lbl(2, "Condition type:")
        self._ctype_var = tk.StringVar(value=_CONDITION_TYPES[0])
        ttk.Combobox(
            frame,
            textvariable=self._ctype_var,
            values=_CONDITION_TYPES,
            state="readonly",
            width=28,
        ).grid(row=2, column=1, sticky="ew", **pad)

        _lbl(3, "Condition value:")
        self._cvalue_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._cvalue_var, width=30).grid(
            row=3, column=1, sticky="ew", **pad
        )
        ttk.Label(
            frame,
            text='For "custom expression", use p as the prompt variable.\n'
            'Example: len(p) > 500 or "translate" in p.lower()',
            foreground="gray",
            font=tkfont.Font(size=8),
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=8)

        _lbl(5, "Priority (≥ 0):")
        self._priority_var = tk.StringVar(value="0")
        ttk.Entry(frame, textvariable=self._priority_var, width=10).grid(
            row=5, column=1, sticky="w", **pad
        )

        _lbl(6, "Cost / 1k tokens ($):")
        self._cost_var = tk.StringVar(value="0.0")
        ttk.Entry(frame, textvariable=self._cost_var, width=10).grid(
            row=6, column=1, sticky="w", **pad
        )

        _lbl(7, "Tags (comma-separated):")
        self._tags_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._tags_var, width=30).grid(
            row=7, column=1, sticky="ew", **pad
        )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="Add", command=self._on_add).pack(
            side="left", padx=4
        )

    def _on_add(self) -> None:
        name = self._name_var.get().strip()
        model = self._model_var.get().strip()
        ctype = self._ctype_var.get()
        cvalue = self._cvalue_var.get()

        if not name:
            messagebox.showerror("Validation error", "Name is required.", parent=self)
            return
        if not model:
            messagebox.showerror("Validation error", "Model is required.", parent=self)
            return

        try:
            condition = _build_condition(ctype, cvalue)
        except ValueError as exc:
            messagebox.showerror("Condition error", str(exc), parent=self)
            return

        try:
            priority = int(self._priority_var.get())
        except ValueError:
            messagebox.showerror(
                "Validation error", "Priority must be an integer.", parent=self
            )
            return

        try:
            cost = float(self._cost_var.get())
        except ValueError:
            messagebox.showerror(
                "Validation error", "Cost must be a number.", parent=self
            )
            return

        tags_raw = self._tags_var.get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        try:
            self._router.add_route(
                name,
                model,
                condition,
                priority=priority,
                cost_per_1k=cost,
                tags=tags,
            )
        except ValueError as exc:
            messagebox.showerror("Router error", str(exc), parent=self)
            return

        self.destroy()


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class RouterApp:
    """Interactive modelrouter editor and tester."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("modelrouter – interactive route editor")
        self.root.minsize(780, 480)
        self.router = Modelrouter(default="gpt-4o-mini")
        self._build_ui()
        self._refresh_table()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(1, weight=1)

        # ── Header bar ──────────────────────────────────────────────────
        header = ttk.Frame(self.root, padding=(8, 6))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, text="Default model:").pack(side="left")
        self._default_var = tk.StringVar(value=self.router.default)
        ttk.Entry(header, textvariable=self._default_var, width=20).pack(
            side="left", padx=(4, 2)
        )
        ttk.Button(header, text="Update", command=self._update_default).pack(
            side="left"
        )

        ttk.Separator(self.root, orient="horizontal").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(36, 0)
        )

        # ── Left panel: route table ──────────────────────────────────────
        left = ttk.LabelFrame(self.root, text="Routes", padding=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        cols = ("Name", "Model", "Priority", "Cost/1k", "Tags")
        self._tree = ttk.Treeview(left, columns=cols, show="headings", height=14)
        for col in cols:
            self._tree.heading(col, text=col)
        self._tree.column("Name", width=110)
        self._tree.column("Model", width=130)
        self._tree.column("Priority", width=65, anchor="center")
        self._tree.column("Cost/1k", width=70, anchor="center")
        self._tree.column("Tags", width=120)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        btn_row = ttk.Frame(left)
        btn_row.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="w")
        ttk.Button(btn_row, text="+ Add Route", command=self._on_add).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="Remove Selected", command=self._on_remove).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="Clear All", command=self._on_clear).pack(
            side="left"
        )

        # ── Right panel: test ────────────────────────────────────────────
        right = ttk.LabelFrame(self.root, text="Test Routing", padding=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Prompt:").grid(row=0, column=0, sticky="w")
        self._prompt_text = tk.Text(right, height=5, wrap="word")
        self._prompt_text.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        ttk.Button(right, text="Resolve →", command=self._on_resolve).grid(
            row=2, column=0, sticky="ew"
        )

        ttk.Separator(right, orient="horizontal").grid(
            row=3, column=0, sticky="ew", pady=8
        )

        ttk.Label(right, text="Result:").grid(row=4, column=0, sticky="w")
        self._result_frame = ttk.Frame(right)
        self._result_frame.grid(row=5, column=0, sticky="nsew")
        right.rowconfigure(5, weight=1)

        self._result_vars: dict[str, tk.StringVar] = {}
        for i, key in enumerate(("Model", "Reason", "Priority", "Matched", "Cost/1k")):
            ttk.Label(self._result_frame, text=f"{key}:", width=10, anchor="w").grid(
                row=i, column=0, sticky="w", pady=2
            )
            var = tk.StringVar(value="—")
            self._result_vars[key] = var
            ttk.Label(
                self._result_frame,
                textvariable=var,
                foreground="#1a56db",
                font=tkfont.Font(weight="bold"),
                anchor="w",
            ).grid(row=i, column=1, sticky="w", padx=(4, 0), pady=2)

        # ── Status bar ───────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self.root,
            textvariable=self._status_var,
            foreground="gray",
            font=tkfont.Font(size=8),
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _update_default(self) -> None:
        new_default = self._default_var.get().strip()
        if not new_default:
            messagebox.showerror("Error", "Default model name must not be empty.")
            return
        cost = self.router._default_cost
        routes_snapshot = self.router.routes()
        self.router = Modelrouter(default=new_default, default_cost_per_1k=cost)
        for r in routes_snapshot:
            self.router.add_route(
                r.name,
                r.model,
                r.condition,
                priority=r.priority,
                cost_per_1k=r.cost_per_1k,
                tags=list(r.tags),
            )
        self._status_var.set(f"Default model updated to {new_default!r}.")

    def _on_add(self) -> None:
        _AddRouteDialog(self.root, self.router)
        self._refresh_table()
        self._status_var.set(f"{len(self.router)} route(s) registered.")

    def _on_remove(self) -> None:
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("Nothing selected", "Select a route to remove.")
            return
        name = self._tree.item(selected[0], "values")[0]
        if messagebox.askyesno("Confirm", f"Remove route {name!r}?"):
            self.router.remove_route(name)
            self._refresh_table()
            self._status_var.set(f"Removed route {name!r}.")

    def _on_clear(self) -> None:
        if not self.router.routes():
            return
        if messagebox.askyesno("Confirm", "Remove all routes?"):
            self.router.clear()
            self._refresh_table()
            self._status_var.set("All routes cleared.")

    def _on_resolve(self) -> None:
        prompt = self._prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("Empty prompt", "Enter a prompt to test.")
            return
        info = self.router.explain(prompt)
        _, cost = self.router.resolve_with_cost(prompt)
        self._result_vars["Model"].set(info["model"])
        self._result_vars["Reason"].set(info["reason"])
        self._result_vars["Priority"].set(
            str(info["priority"]) if info["matched"] else "—"
        )
        self._result_vars["Matched"].set("Yes" if info["matched"] else "No (default)")
        self._result_vars["Cost/1k"].set(f"${cost:.4f}")
        self._status_var.set(
            f"Resolved to {info['model']!r} via {info['reason']!r}."
        )

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for r in self.router.routes():
            self._tree.insert(
                "",
                "end",
                values=(
                    r.name,
                    r.model,
                    r.priority,
                    f"${r.cost_per_1k:.4f}",
                    ", ".join(r.tags) if r.tags else "—",
                ),
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the modelrouter GUI."""
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass
    app = RouterApp(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
