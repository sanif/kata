"""Add Project Wizard screen for TUI."""

from pathlib import Path
from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from kata.core.models import Project, ProjectType
from kata.core.templates import LayoutPreset, write_template
from kata.services.registry import DuplicatePathError, get_registry
from kata.utils.detection import detect_project_type
from kata.utils.paths import PathValidationError, validate_project_path


class WizardStep(Vertical):
    """Base container for wizard steps."""

    DEFAULT_CSS = """
    WizardStep {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }

    WizardStep .step-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    WizardStep .step-description {
        color: $text-muted;
        margin-bottom: 1;
    }
    """


class PathStep(WizardStep):
    """Step 1: Path selection."""

    DEFAULT_CSS = """
    PathStep #path-input {
        margin-bottom: 1;
    }

    PathStep #path-tree {
        height: 1fr;
        border: solid $surface-lighten-1;
    }

    PathStep .path-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    class PathSelected(Message):
        """Message when path is selected."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def compose(self) -> ComposeResult:
        """Compose the step."""
        yield Static("Step 1: Select Project Path", classes="step-title")
        yield Static(
            "Enter a path or browse to select a project directory:",
            classes="step-description",
        )
        yield Input(placeholder="Enter path or browse below...", id="path-input")
        yield DirectoryTree(str(Path.home()), id="path-tree")
        yield Static(
            "Press Enter to select the highlighted directory", classes="path-hint"
        )

    def on_mount(self) -> None:
        """Set initial path to current directory."""
        self.query_one("#path-input", Input).value = str(Path.cwd())

    @on(DirectoryTree.DirectorySelected)
    def on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection from tree."""
        self.query_one("#path-input", Input).value = str(event.path)

    def get_path(self) -> Path:
        """Get the selected path."""
        path_str = self.query_one("#path-input", Input).value.strip()
        if path_str:
            return Path(path_str).expanduser().resolve()
        return Path.cwd()

    def focus_input(self) -> None:
        """Focus the path input."""
        self.query_one("#path-input", Input).focus()


class GroupStep(WizardStep):
    """Step 2: Group selection."""

    DEFAULT_CSS = """
    GroupStep #group-input {
        margin-bottom: 1;
    }

    GroupStep #existing-groups {
        height: auto;
        max-height: 10;
        border: solid $surface-lighten-1;
    }

    GroupStep .group-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the step."""
        yield Static("Step 2: Select Group", classes="step-title")
        yield Static(
            "Enter a new group name or select from existing groups:",
            classes="step-description",
        )
        yield Input(value="Uncategorized", placeholder="Group name...", id="group-input")

        # Get existing groups
        registry = get_registry()
        groups = registry.get_groups()

        if groups:
            yield Static("Existing groups:", classes="group-hint")
            options = [Option(g) for g in sorted(groups)]
            yield OptionList(*options, id="existing-groups")

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle group selection from list."""
        if event.option.prompt:
            self.query_one("#group-input", Input).value = str(event.option.prompt)

    def get_group(self) -> str:
        """Get the selected group."""
        return self.query_one("#group-input", Input).value.strip() or "Uncategorized"

    def focus_input(self) -> None:
        """Focus the group input."""
        self.query_one("#group-input", Input).focus()


class TemplateStep(WizardStep):
    """Step 3: Template selection."""

    DEFAULT_CSS = """
    TemplateStep #template-list {
        height: auto;
        max-height: 12;
        border: solid $surface-lighten-1;
    }

    TemplateStep .detected-type {
        color: $success;
        margin-top: 1;
    }
    """

    project_type: reactive[ProjectType] = reactive(ProjectType.GENERIC)

    def __init__(
        self,
        project_path: Path | None = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize template step."""
        super().__init__(*args, **kwargs)
        self._project_path = project_path

    def compose(self) -> ComposeResult:
        """Compose the step."""
        yield Static("Step 3: Select Template", classes="step-title")
        yield Static(
            "Choose a template for the tmux session layout:",
            classes="step-description",
        )

        options = [
            Option("Auto-detect (Recommended)", id="auto"),
            Option("Python (Editor, Shell, Tests)", id="python"),
            Option("Node.js (Editor, Dev, Tests)", id="node"),
            Option("Go (Editor, Shell, Tests)", id="go"),
            Option("Generic (Editor only)", id="generic"),
        ]
        yield OptionList(*options, id="template-list")

        # Show detected type
        if self._project_path:
            detected = detect_project_type(self._project_path)
            yield Static(
                f"Detected project type: [bold]{detected.value.title()}[/bold]",
                classes="detected-type",
            )
            self.project_type = detected

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle template selection."""
        option_id = event.option.id
        if option_id == "auto":
            if self._project_path:
                self.project_type = detect_project_type(self._project_path)
            else:
                self.project_type = ProjectType.GENERIC
        elif option_id == "python":
            self.project_type = ProjectType.PYTHON
        elif option_id == "node":
            self.project_type = ProjectType.NODE
        elif option_id == "go":
            self.project_type = ProjectType.GO
        else:
            self.project_type = ProjectType.GENERIC

    def set_project_path(self, path: Path) -> None:
        """Update the project path for detection."""
        self._project_path = path
        self.project_type = detect_project_type(path)

    def get_template(self) -> ProjectType:
        """Get the selected template type."""
        return self.project_type

    def focus_input(self) -> None:
        """Focus the template list."""
        self.query_one("#template-list", OptionList).focus()


class LayoutStep(WizardStep):
    """Step 4: Layout preset selection."""

    DEFAULT_CSS = """
    LayoutStep #layout-list {
        height: auto;
        max-height: 8;
        border: solid $surface-lighten-1;
    }

    LayoutStep #layout-preview {
        margin-top: 1;
        padding: 1;
        background: $surface;
        border: solid $surface-lighten-1;
        height: auto;
    }

    LayoutStep .preview-title {
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    layout_preset: reactive[LayoutPreset] = reactive(LayoutPreset.STANDARD)

    def compose(self) -> ComposeResult:
        """Compose the step."""
        yield Static("Step 4: Choose Layout", classes="step-title")
        yield Static(
            "Select how many windows and panes to create:",
            classes="step-description",
        )

        options = [
            Option("Minimal (1 window)", id="minimal"),
            Option("Standard (3 windows) - Recommended", id="standard"),
            Option("Full (5 windows, multi-pane)", id="full"),
            Option("Custom (edit YAML after)", id="custom"),
        ]
        yield OptionList(*options, id="layout-list")

        yield Static("Preview:", classes="preview-title")
        yield Static(id="layout-preview")

    def on_mount(self) -> None:
        """Initialize preview."""
        self._update_preview()
        # Select standard by default
        try:
            option_list = self.query_one("#layout-list", OptionList)
            option_list.highlighted = 1  # Standard is second option
        except Exception:
            pass

    def watch_layout_preset(self, preset: LayoutPreset) -> None:
        """React to layout preset changes."""
        if self.is_mounted:
            self._update_preview()

    def _update_preview(self) -> None:
        """Update the ASCII preview based on selected layout."""
        try:
            preview = self.query_one("#layout-preview", Static)
            preview.update(self._render_preview(self.layout_preset))
        except Exception:
            pass

    def _render_preview(self, preset: LayoutPreset) -> str:
        """Render ASCII art preview for a layout preset."""
        if preset == LayoutPreset.MINIMAL:
            return (
                "[dim]┌────────────┐[/dim]\n"
                "[dim]│[/dim]   editor   [dim]│[/dim]\n"
                "[dim]└────────────┘[/dim]"
            )
        elif preset == LayoutPreset.STANDARD:
            return (
                "[dim]┌────────┐ ┌───────┐ ┌───────┐[/dim]\n"
                "[dim]│[/dim] editor [dim]│ │[/dim] shell [dim]│ │[/dim] tests [dim]│[/dim]\n"
                "[dim]└────────┘ └───────┘ └───────┘[/dim]"
            )
        elif preset == LayoutPreset.FULL:
            return (
                "[dim]┌────────┬────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐[/dim]\n"
                "[dim]│[/dim] editor [dim]│[/dim]git [dim]│ │[/dim] shell [dim]│ │[/dim] tests [dim]│ │[/dim] build [dim]│ │[/dim] logs  [dim]│[/dim]\n"
                "[dim]└────────┴────┘ └───────┘ └───────┘ └───────┘ └───────┘[/dim]"
            )
        else:  # CUSTOM
            return (
                "[dim]┌────────────┐[/dim]\n"
                "[dim]│[/dim]   editor   [dim]│[/dim]  [yellow]← Edit YAML after creation[/yellow]\n"
                "[dim]└────────────┘[/dim]"
            )

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle layout selection."""
        option_id = event.option.id
        if option_id == "minimal":
            self.layout_preset = LayoutPreset.MINIMAL
        elif option_id == "standard":
            self.layout_preset = LayoutPreset.STANDARD
        elif option_id == "full":
            self.layout_preset = LayoutPreset.FULL
        else:
            self.layout_preset = LayoutPreset.CUSTOM

    @on(OptionList.OptionHighlighted)
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Update preview when option is highlighted."""
        option_id = event.option.id
        if option_id == "minimal":
            self.layout_preset = LayoutPreset.MINIMAL
        elif option_id == "standard":
            self.layout_preset = LayoutPreset.STANDARD
        elif option_id == "full":
            self.layout_preset = LayoutPreset.FULL
        else:
            self.layout_preset = LayoutPreset.CUSTOM

    def get_layout(self) -> LayoutPreset:
        """Get the selected layout preset."""
        return self.layout_preset

    def focus_input(self) -> None:
        """Focus the layout list."""
        self.query_one("#layout-list", OptionList).focus()


class AddWizard(ModalScreen):
    """Modal wizard for adding a new project."""

    CSS = """
    AddWizard {
        align: center middle;
    }

    AddWizard #wizard-container {
        width: 70%;
        min-width: 60;
        max-width: 100;
        height: 80%;
        min-height: 20;
        max-height: 30;
        background: $surface;
        border: solid $surface-lighten-1;
        padding: 1;
    }

    AddWizard #wizard-header {
        height: auto;
        margin-bottom: 1;
    }

    AddWizard #wizard-title {
        text-style: bold;
        color: $text;
        text-align: center;
    }

    AddWizard #step-indicator {
        text-align: center;
        color: $text-muted;
    }

    AddWizard #wizard-content {
        height: 1fr;
    }

    AddWizard #wizard-footer {
        height: 3;
        margin-top: 1;
    }

    AddWizard #wizard-buttons {
        align: right middle;
    }

    AddWizard Button {
        margin-left: 1;
    }

    /* Initially hide steps 2-4, show only step 1 */
    AddWizard #group-step {
        display: none;
    }

    AddWizard #template-step {
        display: none;
    }

    AddWizard #layout-step {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    class ProjectAdded(Message):
        """Message when project is added successfully."""

        def __init__(self, project: Project) -> None:
            super().__init__()
            self.project = project

    current_step: reactive[int] = reactive(1)
    _path: Path | None = None
    _group: str = "Uncategorized"
    _initial_path: str | None = None

    def __init__(
        self,
        initial_path: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the wizard.

        Args:
            initial_path: Optional path to pre-fill (e.g., from zoxide entry)
        """
        super().__init__(name=name, id=id, classes=classes)
        self._initial_path = initial_path

    def compose(self) -> ComposeResult:
        """Compose the wizard."""
        with Vertical(id="wizard-container"):
            with Vertical(id="wizard-header"):
                yield Static("Add New Project", id="wizard-title")
                yield Static("Step 1 of 4", id="step-indicator")

            with Container(id="wizard-content"):
                yield PathStep(id="path-step")
                yield GroupStep(id="group-step")
                yield TemplateStep(id="template-step")
                yield LayoutStep(id="layout-step")

            with Horizontal(id="wizard-footer"):
                with Horizontal(id="wizard-buttons"):
                    yield Button("Cancel", variant="default", id="cancel-btn")
                    yield Button("Back", variant="default", id="back-btn")
                    yield Button("Next", variant="primary", id="next-btn")

    def on_mount(self) -> None:
        """Set up initial state."""
        self._update_step_visibility()
        # Pre-fill path if provided
        if self._initial_path:
            try:
                path_step = self.query_one("#path-step", PathStep)
                path_input = path_step.query_one("#path-input", Input)
                path_input.value = self._initial_path
            except Exception:
                pass

    def watch_current_step(self, step: int) -> None:
        """React to step changes."""
        self._update_step_visibility()

    def _update_step_visibility(self) -> None:
        """Show/hide steps based on current step."""
        step = self.current_step

        # Update step indicator
        try:
            indicator = self.query_one("#step-indicator", Static)
            indicator.update(f"Step {step} of 4")
        except Exception:
            pass

        # Show/hide steps and focus active step
        step_classes = [PathStep, GroupStep, TemplateStep, LayoutStep]
        step_ids = ["#path-step", "#group-step", "#template-step", "#layout-step"]
        for i, (step_id, step_class) in enumerate(zip(step_ids, step_classes), 1):
            try:
                step_widget = self.query_one(step_id, step_class)
                step_widget.display = i == step
                # Focus the active step's input
                if i == step:
                    self.call_later(step_widget.focus_input)
            except Exception:
                pass

        # Update buttons
        try:
            back_btn = self.query_one("#back-btn", Button)
            next_btn = self.query_one("#next-btn", Button)

            back_btn.disabled = step == 1
            next_btn.label = "Add Project" if step == 4 else "Next"
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        """Display an error message."""
        self.app.notify(message, severity="error", title="Error")

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel(self) -> None:
        """Handle cancel button."""
        self.dismiss(None)

    @on(Button.Pressed, "#back-btn")
    def on_back(self) -> None:
        """Handle back button."""
        if self.current_step > 1:
            self.current_step -= 1

    @on(Button.Pressed, "#next-btn")
    def on_next(self) -> None:
        """Handle next button."""
        if self.current_step == 1:
            # Validate path
            path_step = self.query_one("#path-step", PathStep)
            try:
                path = path_step.get_path()
                validated_path = validate_project_path(path)
                self._path = validated_path

                # Check for duplicate
                registry = get_registry()
                if registry.find_by_path(validated_path):
                    self._show_error("This path is already registered")
                    return

                # Update template step with detected type
                template_step = self.query_one("#template-step", TemplateStep)
                template_step.set_project_path(validated_path)

                self.current_step = 2
            except PathValidationError as e:
                self._show_error(str(e))

        elif self.current_step == 2:
            # Save group and move to next step
            group_step = self.query_one("#group-step", GroupStep)
            self._group = group_step.get_group()
            self.current_step = 3

        elif self.current_step == 3:
            # Move to layout step
            self.current_step = 4

        elif self.current_step == 4:
            # Add project
            self._add_project()

    def _add_project(self) -> None:
        """Add the project to registry."""
        if not self._path:
            self._show_error("No path selected")
            return

        template_step = self.query_one("#template-step", TemplateStep)
        project_type = template_step.get_template()

        layout_step = self.query_one("#layout-step", LayoutStep)
        layout_preset = layout_step.get_layout()

        # Create project
        project = Project.from_path(self._path, group=self._group)

        # Add to registry
        registry = get_registry()
        try:
            registry.add(project)
        except DuplicatePathError as e:
            self._show_error(str(e))
            return

        # Generate template with layout preset
        config_path = write_template(project, project_type, layout_preset)

        # If custom layout, open editor after creation
        if layout_preset == LayoutPreset.CUSTOM:
            self.app.notify(f"Edit config at: {config_path}", title="Custom Layout")

        # Dismiss with success
        self.post_message(self.ProjectAdded(project))
        self.dismiss(project)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in any input field - advance to next step."""
        self.on_next()

    @on(OptionList.OptionSelected, "#template-list")
    def on_template_list_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle Enter on template list - advance to next step."""
        # Let the step handler update the value first, then advance
        self.call_later(self.on_next)

    @on(OptionList.OptionSelected, "#layout-list")
    def on_layout_list_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle Enter on layout list - add project."""
        # Let the step handler update the value first, then add project
        self.call_later(self.on_next)
