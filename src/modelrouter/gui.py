"""Tkinter GUI for interactive management and testing of a Modelrouter instance."""
import re
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Optional

from .router import Modelrouter

__all__ = ["RouterGUI", "launch"]

# ---------------------------------------------------------------------------
# Condition templates: name → (argument_label, factory(arg) → condition)
# ---------------------------------------------------------------------------
_TEMPLATES = {
    "Contains (case-insensitive)": (
        "Keyword",
        lambda kw: lambda p: kw.lower() in p.lower(),
    ),
    "Starts with": (
        "Prefix",
        lambda kw: lambda p: p.lower().startswith(kw.lower()),
    ),
    "Ends with": (
        "Suffix",
        lambda kw: lambda p: p.lower().endswith(kw.lower()),
    ),
    "Length >": (
        "N",
        lambda kw: lambda p: len(p) > int(kw),
    ),
    "Length <": (
        "N",
        lambda kw: lambda p: len(p) < int(kw),
    ),
    "Regex match": (
        "Pattern",
        lambda kw: lambda p: bool(re.search(kw, p)),
    ),
    "Always": (
        "",
        lambda kw: lambda p: True,
    ),
}

_TEMPLATE_NAMES = list(_TEMPLATES)


class RouterGUI:
    """Interactive Tkinter GUI for a :class:`~modelrouter.Modelrouter` instance.

    Args:
        router: Existing router to inspect and edit.  A new router with the
            ``gpt-4o-mini`` default is created when *None* is supplied.

    Examples:
        >>> from modelrouter import Modelrouter
        >>> from modelrouter.gui import RouterGUI
        >>> gui = RouterGUI(Modelrouter())
        >>> gui.run()          # starts the Tk event loop
    """

    def __init__(self, router: Optional[Modelrouter] = None):
        self.router = router if router is not None else Modelrouter()
        self.root = tk.Tk()
        self.root.title("Modelrouter GUI")
        self.root.minsize(860, 520)
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        routes_tab = ttk.Frame(nb)
        nb.add(routes_tab, text="Routes")
        self._build_routes_tab(routes_tab)

        tester_tab = ttk.Frame(nb)
        nb.add(tester_tab, text="Tester")
        self._build_tester_tab(tester_tab)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom", padx=8, pady=(0, 4))
        self._status_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self._status_var,
                  foreground="gray").pack(side="left")
        self._refresh_status()

    def _build_routes_tab(self, parent: ttk.Frame) -> None:
        pane = ttk.PanedWindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=4, pady=4)

        # ---- left: route list ----
        list_frame = ttk.LabelFrame(pane, text="Registered routes")
        pane.add(list_frame, weight=3)

        cols = ("name", "model", "priority", "cost/1k", "tags")
        self._tree = ttk.Treeview(list_frame, columns=cols,
                                   show="headings", height=14)
        widths = {"name": 110, "model": 130, "priority": 70,
                  "cost/1k": 80, "tags": 140}
        for col in cols:
            self._tree.heading(col, text=col.capitalize())
            self._tree.column(col, width=widths[col], anchor="center")
        self._tree.pack(fill="both", expand=True, padx=4, pady=4)

        btn_row = ttk.Frame(list_frame)
        btn_row.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(btn_row, text="Remove selected",
                   command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Clear all",
                   command=self._clear_all).pack(side="left", padx=2)

        default_row = ttk.Frame(list_frame)
        default_row.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Label(default_row, text="Default model:").pack(side="left")
        self._default_var = tk.StringVar(value=self.router.default)
        ttk.Label(default_row, textvariable=self._default_var,
                  foreground="#555").pack(side="left", padx=6)

        # ---- right: add-route form ----
        form = ttk.LabelFrame(pane, text="Add route")
        pane.add(form, weight=2)

        self._name_var = tk.StringVar()
        self._model_var = tk.StringVar()
        self._priority_var = tk.StringVar(value="0")
        self._cost_var = tk.StringVar(value="0.0")
        self._tags_var = tk.StringVar()

        fields = [
            ("Name *", self._name_var),
            ("Model *", self._model_var),
            ("Priority", self._priority_var),
            ("Cost / 1k ($)", self._cost_var),
            ("Tags (csv)", self._tags_var),
        ]
        for label, var in fields:
            row = ttk.Frame(form)
            row.pack(fill="x", padx=8, pady=3)
            ttk.Label(row, text=label, width=14, anchor="w").pack(side="left")
            ttk.Entry(row, textvariable=var, width=22).pack(side="left")

        # condition selector
        sep = ttk.Separator(form, orient="horizontal")
        sep.pack(fill="x", padx=8, pady=6)

        cond_row = ttk.Frame(form)
        cond_row.pack(fill="x", padx=8, pady=3)
        ttk.Label(cond_row, text="Condition", width=14, anchor="w").pack(side="left")
        self._cond_type_var = tk.StringVar(value=_TEMPLATE_NAMES[0])
        cond_combo = ttk.Combobox(
            cond_row,
            textvariable=self._cond_type_var,
            values=_TEMPLATE_NAMES,
            width=24,
            state="readonly",
        )
        cond_combo.pack(side="left")
        cond_combo.bind("<<ComboboxSelected>>", self._on_cond_change)

        kw_row = ttk.Frame(form)
        kw_row.pack(fill="x", padx=8, pady=3)
        self._kw_label_var = tk.StringVar(value=_TEMPLATES[_TEMPLATE_NAMES[0]][0])
        self._kw_label_widget = ttk.Label(
            kw_row, textvariable=self._kw_label_var, width=14, anchor="w"
        )
        self._kw_label_widget.pack(side="left")
        self._kw_var = tk.StringVar()
        self._kw_entry = ttk.Entry(kw_row, textvariable=self._kw_var, width=22)
        self._kw_entry.pack(side="left")
        self._update_kw_state()

        ttk.Button(form, text="Add route",
                   command=self._add_route).pack(pady=10)

        self._refresh_tree()

    def _build_tester_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Prompt:").pack(side="left")
        self._prompt_var = tk.StringVar()
        prompt_entry = ttk.Entry(top, textvariable=self._prompt_var, width=56)
        prompt_entry.pack(side="left", padx=6)
        prompt_entry.bind("<Return>", lambda _e: self._test_route())
        ttk.Button(top, text="Route  ▶", command=self._test_route).pack(side="left")

        result_frame = ttk.LabelFrame(parent, text="Routing decision")
        result_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self._result_text = scrolledtext.ScrolledText(
            result_frame, height=18, state="disabled", wrap="word",
            font=("Courier", 10),
        )
        self._result_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_cond_change(self, _event: Optional[object] = None) -> None:
        self._update_kw_state()

    def _update_kw_state(self) -> None:
        label, _ = _TEMPLATES[self._cond_type_var.get()]
        self._kw_label_var.set(label if label else "")
        if label:
            self._kw_entry.config(state="normal")
        else:
            self._kw_var.set("")
            self._kw_entry.config(state="disabled")

    def _add_route(self) -> None:
        name = self._name_var.get().strip()
        model = self._model_var.get().strip()

        try:
            priority = int(self._priority_var.get())
        except ValueError:
            messagebox.showerror("Validation error", "Priority must be an integer.")
            return

        try:
            cost = float(self._cost_var.get())
        except ValueError:
            messagebox.showerror("Validation error", "Cost must be a number.")
            return

        tags = [t.strip() for t in self._tags_var.get().split(",") if t.strip()]

        label, cond_factory = _TEMPLATES[self._cond_type_var.get()]
        kw = self._kw_var.get().strip()
        if label and not kw:
            messagebox.showerror("Validation error",
                                 f"'{label}' must not be empty for the selected condition.")
            return

        # Validate numeric argument for Length conditions
        if label == "N":
            try:
                int(kw)
            except ValueError:
                messagebox.showerror("Validation error",
                                     "Length threshold N must be an integer.")
                return

        try:
            condition = cond_factory(kw)
            self.router.add_route(
                name=name, model=model, condition=condition,
                priority=priority, cost_per_1k=cost, tags=tags,
            )
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Error", str(exc))
            return

        # Reset form fields, keep condition type
        self._name_var.set("")
        self._model_var.set("")
        self._tags_var.set("")
        self._refresh_tree()
        self._refresh_status()

    def _remove_selected(self) -> None:
        for item in self._tree.selection():
            self.router.remove_route(item)
        self._refresh_tree()
        self._refresh_status()

    def _clear_all(self) -> None:
        if not messagebox.askyesno("Confirm", "Remove all routes?"):
            return
        self.router.clear_routes()
        self._refresh_tree()
        self._refresh_status()

    def _test_route(self) -> None:
        prompt = self._prompt_var.get()
        exp = self.router.explain(prompt)
        model, cost = self.router.resolve_with_cost(prompt)

        lines = [
            f"Prompt  : {prompt!r}",
            f"Model   : {model}",
            f"Cost/1k : ${cost:.5f}",
            f"Matched : {'yes — ' + exp['reason'] if exp['matched'] else 'no — using default'}",
            f"Priority: {exp['priority'] if exp['matched'] else 'n/a'}",
            "",
            f"{'Route':<20} {'Model':<20} {'Pri':>4}  Match",
            "-" * 56,
        ]
        for r in self.router.routes():
            try:
                hit = bool(r.condition(prompt))
            except Exception:
                hit_str = "ERR"
            else:
                hit_str = "yes" if hit else "no"
            marker = "►" if r.model == model and exp["matched"] and r.name == exp["reason"] else " "
            lines.append(
                f"{marker} {r.name:<18} {r.model:<20} {r.priority:>4}  {hit_str}"
            )
        if not self.router.routes():
            lines.append("  (no routes registered — using default)")

        self._result_text.config(state="normal")
        self._result_text.delete("1.0", "end")
        self._result_text.insert("end", "\n".join(lines))
        self._result_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for r in self.router.routes():
            self._tree.insert(
                "", "end", iid=r.name,
                values=(
                    r.name,
                    r.model,
                    r.priority,
                    f"{r.cost_per_1k:.5f}",
                    ", ".join(r.tags),
                ),
            )

    def _refresh_status(self) -> None:
        n = len(self.router)
        self._status_var.set(
            f"Default: {self.router.default}  |  Routes: {n}"
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter event loop (blocking)."""
        self.root.mainloop()


def launch(router: Optional[Modelrouter] = None) -> None:
    """Open the Modelrouter GUI window.

    Args:
        router: Pre-configured router to display.  A fresh
            :class:`~modelrouter.Modelrouter` is created when *None*.

    Examples:
        >>> from modelrouter import Modelrouter
        >>> from modelrouter.gui import launch
        >>> launch()                      # empty router
        >>> launch(Modelrouter("claude")) # pre-configured router
    """
    RouterGUI(router).run()


if __name__ == "__main__":  # pragma: no cover
    launch()
