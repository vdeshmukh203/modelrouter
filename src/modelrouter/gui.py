"""Tkinter GUI for interactive modelrouter configuration and testing.

Launch the GUI from the command line::

    python -m modelrouter.gui

or from Python::

    from modelrouter.gui import launch
    launch()
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .router import Modelrouter


# ---------------------------------------------------------------------------
# Condition compiler
# ---------------------------------------------------------------------------

def _compile_condition(expr: str):
    """Compile a condition expression string into a callable.

    The expression is evaluated as the body of ``lambda p: <expr>`` where
    *p* is the prompt string.  Examples::

        "code" in p
        len(p) > 2000
        p.startswith("translate")

    Raises
    ------
    ValueError
        If the expression cannot be compiled.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError("Condition expression must not be empty.")
    try:
        fn = eval(f"lambda p: {expr}", {"__builtins__": {}})  # noqa: S307
    except SyntaxError as exc:
        raise ValueError(f"Invalid condition syntax: {exc}") from exc
    if not callable(fn):
        raise ValueError("Compiled condition is not callable.")
    return fn


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class ModelrouterGUI:
    """Interactive GUI for building and testing a :class:`Modelrouter`."""

    def __init__(self, root: tk.Tk, router: Optional[Modelrouter] = None) -> None:
        self.root = root
        self.router = router if router is not None else Modelrouter()
        root.title("modelrouter — route configurator")
        root.resizable(True, True)
        self._build_ui()
        self._refresh_table()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # ── main notebook ────────────────────────────────────────────
        nb = ttk.Notebook(root)
        nb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._tab_routes = ttk.Frame(nb)
        self._tab_test = ttk.Frame(nb)
        nb.add(self._tab_routes, text="  Routes  ")
        nb.add(self._tab_test, text="  Test Prompt  ")

        self._build_routes_tab(self._tab_routes)
        self._build_test_tab(self._tab_test)

        # ── status bar ───────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(root, textvariable=self._status_var, anchor="w",
                  relief="sunken").grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 2))

    # ── Routes tab ──────────────────────────────────────────────────

    def _build_routes_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # ── default model row ────────────────────────────────────────
        def_frame = ttk.LabelFrame(parent, text="Default model", padding=6)
        def_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        def_frame.columnconfigure(1, weight=1)

        ttk.Label(def_frame, text="Model:").grid(row=0, column=0, sticky="w")
        self._default_var = tk.StringVar(value=self.router.default)
        ttk.Entry(def_frame, textvariable=self._default_var, width=28).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        ttk.Label(def_frame, text="Cost/1k $:").grid(row=0, column=2, padx=(10, 0))
        self._default_cost_var = tk.StringVar(value=str(self.router.default_cost))
        ttk.Entry(def_frame, textvariable=self._default_cost_var, width=8).grid(
            row=0, column=3, padx=(4, 0))

        ttk.Button(def_frame, text="Apply", command=self._apply_default).grid(
            row=0, column=4, padx=(8, 0))

        # ── route table ──────────────────────────────────────────────
        tbl_frame = ttk.Frame(parent)
        tbl_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        tbl_frame.columnconfigure(0, weight=1)
        tbl_frame.rowconfigure(0, weight=1)

        cols = ("name", "model", "priority", "cost_per_1k", "tags")
        self._tree = ttk.Treeview(tbl_frame, columns=cols, show="headings",
                                  selectmode="browse")
        widths = {"name": 120, "model": 160, "priority": 70,
                  "cost_per_1k": 80, "tags": 130}
        for c in cols:
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=widths[c], anchor="w")
        self._tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        # ── add/remove form ──────────────────────────────────────────
        form = ttk.LabelFrame(parent, text="Add / update route", padding=6)
        form.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 4))
        for i in range(4):
            form.columnconfigure(i * 2 + 1, weight=1)

        def lbl_entry(row, col, text, var, width=18):
            ttk.Label(form, text=text).grid(row=row, column=col * 2, sticky="w",
                                            padx=(0 if col == 0 else 8, 0))
            e = ttk.Entry(form, textvariable=var, width=width)
            e.grid(row=row, column=col * 2 + 1, sticky="ew")
            return e

        self._f_name = tk.StringVar()
        self._f_model = tk.StringVar()
        self._f_priority = tk.StringVar(value="0")
        self._f_cost = tk.StringVar(value="0.0")
        self._f_tags = tk.StringVar()
        self._f_cond = tk.StringVar()

        lbl_entry(0, 0, "Name:", self._f_name, 16)
        lbl_entry(0, 1, "Model:", self._f_model, 20)
        lbl_entry(0, 2, "Priority:", self._f_priority, 6)
        lbl_entry(0, 3, "Cost/1k $:", self._f_cost, 8)

        ttk.Label(form, text="Condition (lambda p: ...):").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(form, textvariable=self._f_cond).grid(
            row=1, column=1, columnspan=5, sticky="ew", padx=(4, 0), pady=(4, 0))

        ttk.Label(form, text="Tags (comma-sep):").grid(
            row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(form, textvariable=self._f_tags).grid(
            row=2, column=1, columnspan=5, sticky="ew", padx=(4, 0), pady=(4, 0))

        btn_row = ttk.Frame(form)
        btn_row.grid(row=3, column=0, columnspan=8, sticky="e", pady=(6, 0))
        ttk.Button(btn_row, text="Add / Update", command=self._add_route).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Load selected", command=self._load_selected).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Remove selected", command=self._remove_route).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Clear all", command=self._clear_routes).pack(
            side="left")

    # ── Test tab ────────────────────────────────────────────────────

    def _build_test_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        inp_frame = ttk.LabelFrame(parent, text="Prompt", padding=6)
        inp_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        inp_frame.columnconfigure(0, weight=1)

        self._prompt_text = tk.Text(inp_frame, height=5, wrap="word",
                                    font=("TkFixedFont", 10))
        self._prompt_text.grid(row=0, column=0, sticky="ew")
        ttk.Button(inp_frame, text="Route this prompt →",
                   command=self._test_prompt).grid(row=1, column=0, sticky="e",
                                                    pady=(4, 0))

        res_frame = ttk.LabelFrame(parent, text="Routing result", padding=6)
        res_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        res_frame.columnconfigure(0, weight=1)
        res_frame.rowconfigure(0, weight=1)

        self._result_text = tk.Text(res_frame, state="disabled", wrap="word",
                                    font=("TkFixedFont", 10),
                                    background="#f5f5f5")
        self._result_text.grid(row=0, column=0, sticky="nsew")

        vsb2 = ttk.Scrollbar(res_frame, orient="vertical",
                              command=self._result_text.yview)
        self._result_text.configure(yscrollcommand=vsb2.set)
        vsb2.grid(row=0, column=1, sticky="ns")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _apply_default(self) -> None:
        model = self._default_var.get().strip()
        try:
            cost = float(self._default_cost_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Cost/1k must be a number.")
            return
        try:
            self.router.set_default(model, cost)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._set_status(f"Default model set to '{model}'.")

    def _add_route(self) -> None:
        name = self._f_name.get().strip()
        model = self._f_model.get().strip()
        cond_expr = self._f_cond.get().strip()
        tags_raw = self._f_tags.get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        try:
            priority = int(self._f_priority.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Priority must be an integer.")
            return
        try:
            cost = float(self._f_cost.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Cost/1k must be a number.")
            return
        try:
            condition = _compile_condition(cond_expr)
        except ValueError as exc:
            messagebox.showerror("Invalid condition", str(exc))
            return
        try:
            self.router.add_route(name, model, condition, priority, cost, tags)
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self._refresh_table()
        self._set_status(f"Route '{name}' added/updated.")

    def _load_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select a row to load.")
            return
        row = self._tree.item(sel[0], "values")
        name, model, priority, cost, tags = row
        self._f_name.set(name)
        self._f_model.set(model)
        self._f_priority.set(priority)
        self._f_cost.set(cost)
        self._f_tags.set(tags)
        self._f_cond.set("")
        self._set_status(f"Loaded route '{name}' into form.")

    def _remove_route(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Nothing selected", "Select a route to remove.")
            return
        name = self._tree.item(sel[0], "values")[0]
        if not messagebox.askyesno("Confirm", f"Remove route '{name}'?"):
            return
        self.router.remove_route(name)
        self._refresh_table()
        self._set_status(f"Route '{name}' removed.")

    def _clear_routes(self) -> None:
        if not messagebox.askyesno("Confirm", "Remove ALL routes?"):
            return
        self.router.clear_routes()
        self._refresh_table()
        self._set_status("All routes cleared.")

    def _test_prompt(self) -> None:
        prompt = self._prompt_text.get("1.0", "end-1c")
        exp = self.router.explain(prompt)
        lines = [
            f"Model      : {exp['model']}",
            f"Matched    : {exp['matched']}",
            f"Reason     : {exp['reason']}",
            f"Priority   : {exp['priority']}",
            f"Cost/1k $  : {exp['cost_per_1k']}",
            f"Tags       : {', '.join(exp['tags']) if exp['tags'] else '—'}",
        ]
        self._set_result("\n".join(lines))
        self._set_status(
            f"Routed to '{exp['model']}' "
            + ("(matched)" if exp["matched"] else "(default fallback)") + "."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for route in self.router.routes():
            self._tree.insert(
                "",
                "end",
                values=(
                    route.name,
                    route.model,
                    route.priority,
                    route.cost_per_1k,
                    ", ".join(route.tags),
                ),
            )

    def _set_result(self, text: str) -> None:
        self._result_text.configure(state="normal")
        self._result_text.delete("1.0", "end")
        self._result_text.insert("1.0", text)
        self._result_text.configure(state="disabled")

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def launch(router: Optional[Modelrouter] = None) -> None:
    """Open the GUI window (blocks until the window is closed).

    Parameters
    ----------
    router:
        An existing :class:`Modelrouter` instance to edit.  If ``None`` a
        fresh router with the default ``"gpt-4o-mini"`` fallback is created.
    """
    root = tk.Tk()
    root.minsize(660, 480)
    ModelrouterGUI(root, router)
    root.mainloop()


def main() -> None:
    """CLI entry point: ``python -m modelrouter.gui``."""
    launch()


if __name__ == "__main__":
    main()
