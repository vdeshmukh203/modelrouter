"""Tkinter GUI for interactive exploration of Modelrouter configurations."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Dict, Optional

from .router import Modelrouter


# ---------------------------------------------------------------------------
# Condition helpers
# ---------------------------------------------------------------------------

_CONDITION_TYPES = ["contains", "starts_with", "length_gt", "always", "never", "custom"]


def _build_condition(ctype: str, value: str) -> Callable[[str], bool]:
    """Build a condition callable from a type name and string value.

    Args:
        ctype: One of ``contains``, ``starts_with``, ``length_gt``, ``always``,
            ``never``, or ``custom``.
        value: Parameter string for the condition (unused for ``always``/``never``).

    Returns:
        A callable ``(prompt: str) -> bool``.

    Raises:
        ValueError: For unknown *ctype* or non-integer *value* with ``length_gt``.
    """
    if ctype == "contains":
        kw = value.lower()
        return lambda p: kw in p.lower()
    if ctype == "starts_with":
        prefix = value.lower()
        return lambda p: p.lower().startswith(prefix)
    if ctype == "length_gt":
        threshold = int(value)
        return lambda p: len(p) > threshold
    if ctype == "always":
        return lambda p: True
    if ctype == "never":
        return lambda p: False
    if ctype == "custom":
        expr = value
        def _custom(p: str, _e: str = expr) -> bool:
            return bool(eval(_e, {"p": p, "__builtins__": {}}))  # noqa: S307
        return _custom
    raise ValueError(f"Unknown condition type: {ctype!r}")


def _condition_label(ctype: str, value: str) -> str:
    """Return a short human-readable description of a condition."""
    if ctype == "contains":
        return f'contains "{value}"'
    if ctype == "starts_with":
        return f'starts_with "{value}"'
    if ctype == "length_gt":
        return f"len > {value}"
    if ctype in ("always", "never"):
        return ctype
    if ctype == "custom":
        return f"custom: {value}"
    return value


# ---------------------------------------------------------------------------
# GUI class
# ---------------------------------------------------------------------------

class ModelrouterGUI:
    """Interactive Tkinter application for configuring and testing a Modelrouter.

    Args:
        router: An optional pre-configured :class:`Modelrouter` instance.
            A new default router is created when not provided.
    """

    def __init__(self, router: Optional[Modelrouter] = None) -> None:
        self.router = router or Modelrouter()
        # Store condition metadata so we can display it in the table.
        self._route_meta: Dict[str, Dict[str, str]] = {}

        self.root = tk.Tk()
        self.root.title("modelrouter — Route Explorer")
        self.root.geometry("980x700")
        self.root.minsize(720, 520)

        self._build_ui()
        self._refresh_table()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = self._build_left_panel(paned)
        right = self._build_right_panel(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

    def _build_left_panel(self, parent: ttk.PanedWindow) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Default model bar
        self._build_default_bar(frame)

        # Route table
        self._build_route_table(frame)

        # Action buttons
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(btn_row, text="Remove selected",
                   command=self._remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear all",
                   command=self._clear_all).pack(side=tk.LEFT, padx=2)

        return frame

    def _build_default_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.LabelFrame(parent, text="Default model")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        bar.columnconfigure(1, weight=1)

        ttk.Label(bar, text="Model:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self._default_var = tk.StringVar(value=self.router.default)
        ttk.Entry(bar, textvariable=self._default_var).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(bar, text="Apply", command=self._apply_default).grid(
            row=0, column=2, padx=4, pady=4)

    def _build_route_table(self, parent: ttk.Frame) -> None:
        table_frame = ttk.LabelFrame(parent, text="Routes (highest priority first)")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "model", "priority", "cost_1k", "tags", "condition")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse")

        col_cfg = [
            ("name",      "Name",      110, "w"),
            ("model",     "Model",     130, "w"),
            ("priority",  "Priority",   65, "center"),
            ("cost_1k",   "Cost/1k",    75, "center"),
            ("tags",      "Tags",       95, "w"),
            ("condition", "Condition", 170, "w"),
        ]
        for col, heading, width, anchor in col_cfg:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor=anchor, minwidth=50)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    def _build_right_panel(self, parent: ttk.PanedWindow) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self._build_add_form(frame)
        self._build_tester(frame)

        return frame

    def _build_add_form(self, parent: ttk.Frame) -> None:
        form = ttk.LabelFrame(parent, text="Add route")
        form.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        form.columnconfigure(1, weight=1)

        self._form_vars: Dict[str, tk.StringVar] = {}
        fields = [
            ("Name:",       "name",     ""),
            ("Model:",      "model",    ""),
            ("Priority:",   "priority", "0"),
            ("Cost / 1k:", "cost",     "0.0"),
            ("Tags (csv):", "tags",     ""),
        ]
        for row_i, (label, key, default) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row_i, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar(value=default)
            self._form_vars[key] = var
            ttk.Entry(form, textvariable=var).grid(
                row=row_i, column=1, sticky="ew", padx=4, pady=2)

        # Condition type selector
        base = len(fields)
        ttk.Label(form, text="Condition type:").grid(
            row=base, column=0, sticky="w", padx=4, pady=2)
        self._cond_type_var = tk.StringVar(value="contains")
        self._cond_type_var.trace_add("write", self._on_cond_type_change)
        ttk.Combobox(
            form,
            textvariable=self._cond_type_var,
            values=_CONDITION_TYPES,
            state="readonly",
            width=14,
        ).grid(row=base, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(form, text="Value:").grid(
            row=base + 1, column=0, sticky="w", padx=4, pady=2)
        self._cond_value_var = tk.StringVar()
        self._cond_value_entry = ttk.Entry(form, textvariable=self._cond_value_var)
        self._cond_value_entry.grid(
            row=base + 1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(
            form,
            text='For "custom": use "p" as the prompt variable.\nNo builtins available.',
            foreground="gray",
        ).grid(row=base + 2, column=0, columnspan=2, sticky="w", padx=4)

        ttk.Button(form, text="Add route", command=self._add_route).grid(
            row=base + 3, column=0, columnspan=2, pady=6)

    def _build_tester(self, parent: ttk.Frame) -> None:
        tester = ttk.LabelFrame(parent, text="Test prompt")
        tester.grid(row=1, column=0, sticky="nsew")
        tester.columnconfigure(0, weight=1)
        tester.rowconfigure(1, weight=1)
        tester.rowconfigure(4, weight=1)

        ttk.Label(tester, text="Prompt:").grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 0))
        self._prompt_text = scrolledtext.ScrolledText(tester, height=4, wrap=tk.WORD)
        self._prompt_text.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)

        btn_row = ttk.Frame(tester)
        btn_row.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(btn_row, text="Resolve",
                   command=self._do_resolve).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Explain",
                   command=self._do_explain).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Resolve + cost",
                   command=self._do_cost).pack(side=tk.LEFT, padx=2)

        self._result_var = tk.StringVar()
        ttk.Label(
            tester,
            textvariable=self._result_var,
            wraplength=300,
            justify=tk.LEFT,
            foreground="#005a9e",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=3, column=0, sticky="w", padx=4, pady=2)

        ttk.Label(tester, text="Explain output:").grid(
            row=4, column=0, sticky="w", padx=4, pady=(4, 0))
        self._explain_text = scrolledtext.ScrolledText(
            tester, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self._explain_text.grid(row=5, column=0, sticky="nsew", padx=4, pady=(0, 4))
        tester.rowconfigure(5, weight=1)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_cond_type_change(self, *_: object) -> None:
        ctype = self._cond_type_var.get()
        state = tk.DISABLED if ctype in ("always", "never") else tk.NORMAL
        self._cond_value_entry.configure(state=state)

    def _apply_default(self) -> None:
        new_default = self._default_var.get().strip()
        if not new_default:
            messagebox.showerror("Error", "Default model cannot be empty.")
            return
        self.router._default = new_default
        self._refresh_table()

    def _add_route(self) -> None:
        name = self._form_vars["name"].get().strip()
        model = self._form_vars["model"].get().strip()
        ctype = self._cond_type_var.get()
        cvalue = self._cond_value_var.get().strip()

        if not name:
            messagebox.showerror("Validation error", "Route name is required.")
            return
        if not model:
            messagebox.showerror("Validation error", "Model name is required.")
            return
        if ctype in ("contains", "starts_with", "custom") and not cvalue:
            messagebox.showerror(
                "Validation error",
                f"Condition type \"{ctype}\" requires a value.",
            )
            return
        if ctype == "length_gt":
            if not cvalue:
                messagebox.showerror("Validation error", "length_gt requires a value.")
                return
            try:
                int(cvalue)
            except ValueError:
                messagebox.showerror(
                    "Validation error", "length_gt value must be an integer.")
                return

        try:
            priority = int(self._form_vars["priority"].get())
        except ValueError:
            messagebox.showerror("Validation error", "Priority must be an integer.")
            return
        try:
            cost = float(self._form_vars["cost"].get())
        except ValueError:
            messagebox.showerror("Validation error", "Cost must be a number.")
            return

        tags_raw = self._form_vars["tags"].get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        try:
            condition = _build_condition(ctype, cvalue)
        except Exception as exc:
            messagebox.showerror("Condition error", f"Could not build condition:\n{exc}")
            return

        try:
            self.router.add_route(
                name, model, condition,
                priority=priority, cost_per_1k=cost, tags=tags,
            )
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self._route_meta[name] = {"ctype": ctype, "cvalue": cvalue}
        self._refresh_table()
        for key, default in [("name", ""), ("model", ""), ("priority", "0"),
                              ("cost", "0.0"), ("tags", "")]:
            self._form_vars[key].set(default)
        self._cond_value_var.set("")

    def _remove_selected(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a route in the table first.")
            return
        name = str(self._tree.item(sel[0])["values"][0])
        self.router.remove_route(name)
        self._route_meta.pop(name, None)
        self._refresh_table()

    def _clear_all(self) -> None:
        if not messagebox.askyesno("Confirm", "Remove all routes?"):
            return
        self.router.clear()
        self._route_meta.clear()
        self._refresh_table()

    def _do_resolve(self) -> None:
        prompt = self._prompt_text.get("1.0", tk.END).strip()
        model = self.router.resolve(prompt)
        self._result_var.set(f"Model: {model}")
        self._set_explain_text("")

    def _do_explain(self) -> None:
        prompt = self._prompt_text.get("1.0", tk.END).strip()
        result = self.router.explain(prompt)
        self._result_var.set(f"Model: {result['model']}")
        self._set_explain_text(json.dumps(result, indent=2))

    def _do_cost(self) -> None:
        prompt = self._prompt_text.get("1.0", tk.END).strip()
        model, cost = self.router.resolve_with_cost(prompt)
        self._result_var.set(f"Model: {model}   Cost/1k: ${cost:.6f}")
        self._set_explain_text("")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for route in self.router.routes():
            meta = self._route_meta.get(route.name, {})
            cond_str = _condition_label(
                meta.get("ctype", "?"), meta.get("cvalue", ""))
            self._tree.insert("", tk.END, values=(
                route.name,
                route.model,
                route.priority,
                f"${route.cost_per_1k:.4f}",
                ", ".join(route.tags) or "—",
                cond_str,
            ))

    def _set_explain_text(self, text: str) -> None:
        self._explain_text.config(state=tk.NORMAL)
        self._explain_text.delete("1.0", tk.END)
        if text:
            self._explain_text.insert(tk.END, text)
        self._explain_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the GUI event loop (blocking)."""
        self.root.mainloop()


def launch(router: Optional[Modelrouter] = None) -> None:
    """Launch the modelrouter GUI.

    Opens an interactive Tkinter window for configuring routes and testing
    prompts against a :class:`~modelrouter.Modelrouter` instance.

    Args:
        router: An optional pre-configured :class:`Modelrouter` instance.
            A new router with default model ``"gpt-4o-mini"`` is used when
            not provided.

    Example:
        >>> from modelrouter import Modelrouter
        >>> from modelrouter.gui import launch
        >>> router = Modelrouter(default="gpt-4o-mini")
        >>> launch(router)  # opens the GUI window
    """
    ModelrouterGUI(router=router).run()
