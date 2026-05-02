"""Tkinter-based GUI for interacting with a Modelrouter instance.

Launch the interface from the command line::

    python -m modelrouter.gui

or programmatically::

    from modelrouter import Modelrouter
    from modelrouter.gui import launch

    router = Modelrouter(default="gpt-4o-mini")
    launch(router)
"""

import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from .router import Modelrouter, RouteError

# ---------------------------------------------------------------------------
# Condition builder
# ---------------------------------------------------------------------------

_CONDITION_TYPES: list[tuple[str, str]] = [
    ("always", "Always match"),
    ("contains", "Contains text"),
    ("not_contains", "Does not contain text"),
    ("starts_with", "Starts with"),
    ("ends_with", "Ends with"),
    ("length_gt", "Length greater than N"),
    ("length_lt", "Length less than N"),
    ("regex", "Regex match"),
]

_NEEDS_PARAM = {key for key, _ in _CONDITION_TYPES if key != "always"}


def _build_condition(cond_type: str, param: str) -> Callable[[str], bool]:
    """Return a condition callable from a GUI-selected type and string parameter.

    Parameters
    ----------
    cond_type:
        One of the keys in ``_CONDITION_TYPES``.
    param:
        User-supplied string parameter (not used for *always*).

    Raises
    ------
    ValueError
        If *cond_type* is unknown or *param* cannot be parsed.
    re.error
        If *cond_type* is ``"regex"`` and *param* is an invalid pattern.
    """
    if cond_type == "always":
        return lambda p: True
    if cond_type == "contains":
        text = param
        return lambda p: text in p
    if cond_type == "not_contains":
        text = param
        return lambda p: text not in p
    if cond_type == "starts_with":
        prefix = param
        return lambda p: p.startswith(prefix)
    if cond_type == "ends_with":
        suffix = param
        return lambda p: p.endswith(suffix)
    if cond_type == "length_gt":
        try:
            threshold = int(param)
        except ValueError as err:
            raise ValueError(f"Length threshold must be an integer, got {param!r}.") from err
        return lambda p: len(p) > threshold
    if cond_type == "length_lt":
        try:
            threshold = int(param)
        except ValueError as err:
            raise ValueError(f"Length threshold must be an integer, got {param!r}.") from err
        return lambda p: len(p) < threshold
    if cond_type == "regex":
        pattern = re.compile(param)
        return lambda p: bool(pattern.search(p))
    raise ValueError(f"Unknown condition type: {cond_type!r}")


def _cond_label(cond_type: str) -> str:
    for key, label in _CONDITION_TYPES:
        if key == cond_type:
            return label
    return cond_type


# ---------------------------------------------------------------------------
# Main GUI class
# ---------------------------------------------------------------------------


class RouterGUI:
    """Tkinter application window for managing a :class:`~modelrouter.Modelrouter`.

    Parameters
    ----------
    router:
        Pre-configured router instance.  A new empty router is created if
        ``None``.
    """

    _COND_KEYS = [k for k, _ in _CONDITION_TYPES]
    _COND_LABELS = [lbl for _, lbl in _CONDITION_TYPES]

    def __init__(self, router: Optional[Modelrouter] = None) -> None:
        self.router = router if router is not None else Modelrouter()
        self.root = tk.Tk()
        self.root.title("modelrouter — LLM Route Manager")
        self.root.minsize(960, 620)
        self._build_ui()

    # ------------------------------------------------------------------
    # Layout builders
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Registered Routes", font=("", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        # Route table
        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("Name", "Model", "Priority", "Cost/1k", "Tags")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=9)
        widths = {"Name": 110, "Model": 130, "Priority": 65, "Cost/1k": 80, "Tags": 120}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        ttk.Button(parent, text="Remove Selected Route", command=self._remove_route).grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )

        # Add-route form
        form = ttk.LabelFrame(parent, text="Add Route", padding=10)
        form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)

        self._form_vars: dict[str, tk.StringVar] = {}
        simple_fields: list[tuple[str, str, str]] = [
            ("Name", "name", ""),
            ("Model", "model", "gpt-4o-mini"),
            ("Priority (int ≥ 0)", "priority", "0"),
            ("Cost / 1k tokens (USD)", "cost", "0.0"),
            ("Tags (comma-separated)", "tags", ""),
        ]
        for row_idx, (label, key, default) in enumerate(simple_fields):
            ttk.Label(form, text=label + ":").grid(
                row=row_idx, column=0, sticky="e", padx=(0, 6), pady=3
            )
            var = tk.StringVar(value=default)
            self._form_vars[key] = var
            ttk.Entry(form, textvariable=var).grid(row=row_idx, column=1, sticky="ew", pady=3)

        base = len(simple_fields)

        # Condition type
        ttk.Label(form, text="Condition:").grid(row=base, column=0, sticky="e", padx=(0, 6), pady=3)
        self._cond_type_var = tk.StringVar(value=self._COND_LABELS[1])
        self._cond_combo = ttk.Combobox(
            form,
            textvariable=self._cond_type_var,
            values=self._COND_LABELS,
            state="readonly",
            width=24,
        )
        self._cond_combo.grid(row=base, column=1, sticky="ew", pady=3)
        self._cond_combo.bind("<<ComboboxSelected>>", self._on_cond_change)

        # Condition parameter
        ttk.Label(form, text="Condition param:").grid(
            row=base + 1, column=0, sticky="e", padx=(0, 6), pady=3
        )
        self._cond_param_var = tk.StringVar()
        self._cond_param_entry = ttk.Entry(form, textvariable=self._cond_param_var)
        self._cond_param_entry.grid(row=base + 1, column=1, sticky="ew", pady=3)

        ttk.Button(form, text="Add Route", command=self._add_route).grid(
            row=base + 2, column=0, columnspan=2, pady=(10, 0)
        )

    def _build_right(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Test Prompt", font=("", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        self.prompt_text = tk.Text(parent, height=9, wrap="word", relief="solid", borderwidth=1)
        self.prompt_text.grid(row=1, column=0, sticky="nsew", pady=(0, 4))

        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=2, column=0, sticky="w", pady=(0, 6))
        ttk.Button(btn_frame, text="Test Route", command=self._test_prompt).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Clear", command=self._clear_prompt).grid(row=0, column=1)

        # Decision panel
        decision_frame = ttk.LabelFrame(parent, text="Routing Decision", padding=10)
        decision_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        decision_frame.columnconfigure(1, weight=1)

        self._result_vars: dict[str, tk.StringVar] = {}
        result_rows = [
            ("Model", "model"),
            ("Reason / Route", "reason"),
            ("Priority", "priority"),
            ("Matched", "matched"),
            ("Cost / 1k tokens", "cost"),
            ("Tags", "tags"),
        ]
        for i, (label, key) in enumerate(result_rows):
            ttk.Label(decision_frame, text=label + ":").grid(
                row=i, column=0, sticky="e", padx=(0, 10), pady=2
            )
            var = tk.StringVar(value="—")
            self._result_vars[key] = var
            ttk.Label(
                decision_frame, textvariable=var, foreground="#1a56db", font=("", 9, "bold")
            ).grid(row=i, column=1, sticky="w", pady=2)

        # Statistics panel
        stats_frame = ttk.LabelFrame(parent, text="Match Statistics", padding=10)
        stats_frame.grid(row=4, column=0, sticky="ew")
        stats_frame.columnconfigure(0, weight=1)

        self._stats_text = tk.Text(
            stats_frame,
            height=5,
            state="disabled",
            wrap="word",
            relief="flat",
            font=("Courier", 9),
        )
        self._stats_text.grid(row=0, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_cond_change(self, _event: object) -> None:
        label = self._cond_type_var.get()
        idx = self._COND_LABELS.index(label)
        key = self._COND_KEYS[idx]
        state = "normal" if key in _NEEDS_PARAM else "disabled"
        self._cond_param_entry.configure(state=state)
        if state == "disabled":
            self._cond_param_var.set("")

    def _add_route(self) -> None:
        name = self._form_vars["name"].get().strip()
        model = self._form_vars["model"].get().strip()
        priority_raw = self._form_vars["priority"].get().strip() or "0"
        cost_raw = self._form_vars["cost"].get().strip() or "0.0"
        tags_raw = self._form_vars["tags"].get().strip()

        label = self._cond_type_var.get()
        idx = self._COND_LABELS.index(label)
        cond_key = self._COND_KEYS[idx]
        param = self._cond_param_var.get().strip()

        if not name or not model:
            messagebox.showerror("Validation Error", "Name and Model are required.")
            return

        try:
            priority = int(priority_raw)
            cost = float(cost_raw)
        except ValueError:
            messagebox.showerror(
                "Validation Error",
                "Priority must be an integer; Cost must be a decimal number.",
            )
            return

        if cond_key in _NEEDS_PARAM and not param:
            messagebox.showerror(
                "Validation Error",
                f"The condition '{label}' requires a parameter value.",
            )
            return

        try:
            condition = _build_condition(cond_key, param)
        except (ValueError, re.error) as exc:
            messagebox.showerror("Condition Error", str(exc))
            return

        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        try:
            self.router.add_route(
                name,
                model,
                condition,
                priority=priority,
                cost_per_1k=cost,
                tags=tags,
            )
        except (RouteError, ValueError, TypeError) as exc:
            messagebox.showerror("Route Error", str(exc))
            return

        # Reset form (keep model and priority defaults)
        self._form_vars["name"].set("")
        self._form_vars["tags"].set("")
        self._cond_param_var.set("")
        self._refresh_table()

    def _remove_route(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Select a route in the table to remove it.")
            return
        name = str(self.tree.item(selected[0])["values"][0])
        if messagebox.askyesno("Confirm", f"Remove route '{name}'?"):
            self.router.remove_route(name)
            self._refresh_table()
            self._refresh_stats()

    def _test_prompt(self) -> None:
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("Info", "Enter a prompt in the text box above.")
            return
        decision = self.router.explain(prompt)
        self._result_vars["model"].set(decision["model"])
        self._result_vars["reason"].set(decision["reason"])
        self._result_vars["priority"].set(str(decision["priority"]))
        self._result_vars["matched"].set("Yes" if decision["matched"] else "No (default used)")
        cost = decision.get("cost_per_1k", 0.0)
        self._result_vars["cost"].set(f"${cost:.4f}")
        tag_list = decision.get("tags", [])
        self._result_vars["tags"].set(", ".join(tag_list) if tag_list else "—")
        self._refresh_stats()

    def _clear_prompt(self) -> None:
        self.prompt_text.delete("1.0", "end")

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for route in self.router.routes():
            self.tree.insert(
                "",
                "end",
                values=(
                    route.name,
                    route.model,
                    route.priority,
                    f"${route.cost_per_1k:.4f}",
                    ", ".join(route.tags) or "—",
                ),
            )

    def _refresh_stats(self) -> None:
        stats = self.router.statistics()
        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")
        if not stats:
            self._stats_text.insert("end", "  No matches recorded yet.\n")
        else:
            for route_name, count in sorted(stats.items(), key=lambda x: -x[1]):
                bar = "#" * min(count, 30)
                self._stats_text.insert("end", f"  {route_name:<20} {bar} ({count})\n")
        self._stats_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self._refresh_table()
        self._refresh_stats()
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def launch(router: Optional[Modelrouter] = None) -> None:
    """Launch the modelrouter GUI.

    Parameters
    ----------
    router:
        Pre-configured :class:`~modelrouter.Modelrouter` instance.  A fresh
        router with the default model ``"gpt-4o-mini"`` is created when
        ``None`` is passed.

    Examples
    --------
    >>> from modelrouter import Modelrouter
    >>> from modelrouter.gui import launch
    >>> router = Modelrouter(default="gpt-4o-mini")
    >>> router.add_route("code", "gpt-4o", lambda p: "```" in p, priority=10)
    >>> launch(router)   # opens the GUI window
    """
    RouterGUI(router).run()


if __name__ == "__main__":
    launch()
