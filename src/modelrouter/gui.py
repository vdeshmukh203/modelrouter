"""Interactive Tkinter GUI for modelrouter configuration and testing."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from modelrouter.router import DuplicateRouteError, Modelrouter


class _RouteDialog(tk.Toplevel):
    """Modal dialog for adding or editing a single route.

    After the dialog is closed, inspect ``result`` — it is ``None`` if the
    user cancelled, or a dict of route fields otherwise.
    """

    _HELP = (
        "Condition — Python expression using 'p' (the prompt string).\n"
        "Examples:  'code' in p  |  len(p) > 2000  |  p.startswith('explain')"
    )

    def __init__(
        self,
        parent: tk.Misc,
        title: str = "Add Route",
        *,
        name: str = "",
        model: str = "",
        condition_expr: str = "",
        priority: int = 0,
        cost: float = 0.0,
        tags: str = "",
        name_locked: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[dict] = None
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        labels = ["Route name:", "Model:", "Condition (expr):", "Priority:", "Cost / 1k tokens:", "Tags (comma-sep):"]
        defaults = [name, model, condition_expr, str(priority), str(cost), tags]
        self._entries: list[ttk.Entry] = []

        for row, (lbl, val) in enumerate(zip(labels, defaults)):
            ttk.Label(frame, text=lbl).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(frame, width=42)
            entry.insert(0, val)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
            self._entries.append(entry)

        if name_locked:
            self._entries[0].configure(state="disabled")

        ttk.Label(frame, text=self._HELP, foreground="#666", wraplength=340, justify="left").grid(
            row=len(labels), column=0, columnspan=2, pady=(6, 0), sticky="w"
        )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(labels) + 1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_frame, text="OK", width=10, command=self._ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=4)

        self._entries[1].focus_set()
        self.wait_window(self)

    def _ok(self) -> None:
        name, model, cond_expr, priority_s, cost_s, tags_s = (
            e.get().strip() for e in self._entries
        )
        if not name:
            messagebox.showerror("Validation error", "Route name is required.", parent=self)
            return
        if not model:
            messagebox.showerror("Validation error", "Model is required.", parent=self)
            return
        if not cond_expr:
            messagebox.showerror("Validation error", "Condition expression is required.", parent=self)
            return
        try:
            priority = int(priority_s)
        except ValueError:
            messagebox.showerror("Validation error", "Priority must be an integer.", parent=self)
            return
        try:
            cost = float(cost_s)
        except ValueError:
            messagebox.showerror("Validation error", "Cost must be a number.", parent=self)
            return
        try:
            condition_fn = eval(f"lambda p: {cond_expr}", {}, {})  # noqa: S307
            condition_fn("probe")
        except Exception as exc:
            messagebox.showerror("Invalid condition", f"Could not evaluate condition:\n{exc}", parent=self)
            return

        self.result = {
            "name": name,
            "model": model,
            "condition": condition_fn,
            "condition_expr": cond_expr,
            "priority": priority,
            "cost_per_1k": cost,
            "tags": [t.strip() for t in tags_s.split(",") if t.strip()],
        }
        self.destroy()


class ModelrouterApp:
    """Main GUI window for configuring and testing a :class:`Modelrouter`."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Model Router")
        self.root.geometry("960x580")
        self.root.minsize(720, 460)

        self._router = Modelrouter(default="gpt-4o-mini")
        # Stores the human-readable condition expression alongside each route.
        self._cond_exprs: dict[str, str] = {}

        self._build_ui()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(10, 4))

        paned.add(self._build_left(paned), weight=2)
        paned.add(self._build_right(paned), weight=3)

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self._status_var, relief="sunken", anchor="w").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    def _build_left(self, parent: tk.Misc) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Routes", padding=8)

        cols = ("Name", "Model", "Pri", "Cost/1k", "Tags")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = {"Name": 100, "Model": 130, "Pri": 45, "Cost/1k": 68, "Tags": 100}
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=widths[col], anchor="center" if col in ("Pri", "Cost/1k") else "w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        btn_row = ttk.Frame(frame)
        btn_row.grid(row=1, column=0, columnspan=2, pady=(6, 0), sticky="ew")
        ttk.Button(btn_row, text="Add", command=self._add_route).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Edit", command=self._edit_route).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Remove", command=self._remove_route).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Clear all", command=self._clear_routes).pack(side="left", padx=2)

        default_row = ttk.Frame(frame)
        default_row.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        ttk.Label(default_row, text="Default model:").pack(side="left")
        self._default_var = tk.StringVar(value=self._router.default)
        ttk.Entry(default_row, textvariable=self._default_var, width=18).pack(side="left", padx=4)
        ttk.Button(default_row, text="Apply", command=self._apply_default).pack(side="left")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return frame

    def _build_right(self, parent: tk.Misc) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Test Routing", padding=8)

        ttk.Label(frame, text="Prompt:").pack(anchor="w")
        self._prompt = tk.Text(frame, height=6, wrap="word", font=("TkFixedFont", 10))
        self._prompt.pack(fill="x", pady=(2, 0))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=6)
        ttk.Button(btn_row, text="Resolve", command=self._do_resolve).pack(side="left", padx=3)
        ttk.Button(btn_row, text="Explain", command=self._do_explain).pack(side="left", padx=3)
        ttk.Button(btn_row, text="Resolve + Cost", command=self._do_resolve_cost).pack(side="left", padx=3)

        ttk.Label(frame, text="Result:").pack(anchor="w")
        self._result = tk.Text(
            frame,
            height=10,
            wrap="word",
            state="disabled",
            font=("TkFixedFont", 10),
            background="#f4f4f4",
        )
        self._result.pack(fill="both", expand=True, pady=(2, 0))

        return frame

    # ------------------------------------------------------------------
    # Route management actions
    # ------------------------------------------------------------------

    def _add_route(self) -> None:
        dlg = _RouteDialog(self.root, "Add Route")
        if dlg.result is None:
            return
        d = dlg.result
        try:
            self._router.add_route(
                d["name"], d["model"], d["condition"],
                d["priority"], d["cost_per_1k"], d["tags"],
            )
        except DuplicateRouteError as exc:
            messagebox.showerror("Duplicate route", str(exc))
            return
        self._cond_exprs[d["name"]] = d["condition_expr"]
        self._refresh()

    def _edit_route(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a route to edit.")
            return
        name = sel[0]
        route = next((r for r in self._router.routes() if r.name == name), None)
        if route is None:
            return
        dlg = _RouteDialog(
            self.root,
            "Edit Route",
            name=route.name,
            model=route.model,
            condition_expr=self._cond_exprs.get(route.name, ""),
            priority=route.priority,
            cost=route.cost_per_1k,
            tags=", ".join(route.tags),
            name_locked=True,
        )
        if dlg.result is None:
            return
        d = dlg.result
        self._router.update_route(
            name,
            model=d["model"],
            condition=d["condition"],
            priority=d["priority"],
            cost_per_1k=d["cost_per_1k"],
            tags=d["tags"],
        )
        self._cond_exprs[name] = d["condition_expr"]
        self._refresh()

    def _remove_route(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a route to remove.")
            return
        name = sel[0]
        if messagebox.askyesno("Confirm", f"Remove route '{name}'?"):
            self._router.remove_route(name)
            self._cond_exprs.pop(name, None)
            self._refresh()

    def _clear_routes(self) -> None:
        if not self._router.routes():
            return
        if messagebox.askyesno("Confirm", "Remove all routes?"):
            self._router.clear()
            self._cond_exprs.clear()
            self._refresh()

    def _apply_default(self) -> None:
        new_default = self._default_var.get().strip()
        if not new_default:
            messagebox.showerror("Validation error", "Default model cannot be empty.")
            return
        snapshot = [
            (r.name, r.model, r.condition, r.priority, r.cost_per_1k, r.tags)
            for r in self._router.routes()
        ]
        self._router = Modelrouter(default=new_default)
        for name, model, condition, priority, cost, tags in snapshot:
            self._router.add_route(name, model, condition, priority, cost, tags)
        self._refresh()

    # ------------------------------------------------------------------
    # Test routing actions
    # ------------------------------------------------------------------

    def _prompt_text(self) -> Optional[str]:
        text = self._prompt.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo("Empty prompt", "Enter a prompt first.")
            return None
        return text

    def _show_result(self, text: str) -> None:
        self._result.configure(state="normal")
        self._result.delete("1.0", "end")
        self._result.insert("end", text)
        self._result.configure(state="disabled")

    def _do_resolve(self) -> None:
        prompt = self._prompt_text()
        if prompt is None:
            return
        model = self._router.resolve(prompt)
        self._show_result(f"Model: {model}")
        self._status("Resolved → " + model)

    def _do_explain(self) -> None:
        prompt = self._prompt_text()
        if prompt is None:
            return
        exp = self._router.explain(prompt)
        cond = self._cond_exprs.get(exp["reason"], "")
        lines = [
            f"Model     : {exp['model']}",
            f"Matched   : {exp['matched']}",
            f"Reason    : {exp['reason']}",
            f"Priority  : {exp['priority']}",
            f"Cost/1k   : ${exp['cost_per_1k']:.4f}",
            f"Tags      : {', '.join(exp['tags']) or '—'}",
        ]
        if cond:
            lines.append(f"Condition : {cond}")
        self._show_result("\n".join(lines))
        self._status(f"Explained → {exp['model']} via '{exp['reason']}'")

    def _do_resolve_cost(self) -> None:
        prompt = self._prompt_text()
        if prompt is None:
            return
        model, cost = self._router.resolve_with_cost(prompt)
        self._show_result(f"Model     : {model}\nCost/1k   : ${cost:.4f}")
        self._status(f"Resolved → {model} @ ${cost:.4f}/1k")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for route in self._router.routes():
            self._tree.insert(
                "", "end", iid=route.name,
                values=(
                    route.name,
                    route.model,
                    route.priority,
                    f"{route.cost_per_1k:.4f}",
                    ", ".join(route.tags),
                ),
            )
        self._default_var.set(self._router.default)
        self._status(
            f"{len(self._router)} route{'s' if len(self._router) != 1 else ''} | "
            f"default: {self._router.default}"
        )

    def _status(self, msg: str) -> None:
        self._status_var.set(msg)


def launch() -> None:
    """Launch the Model Router GUI."""
    root = tk.Tk()
    ModelrouterApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
