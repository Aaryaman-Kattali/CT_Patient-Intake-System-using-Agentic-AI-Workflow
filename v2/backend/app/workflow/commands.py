"""Everything a user can do on a turn. Buttons never go through the LLM."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Command(BaseModel):
    model_config = ConfigDict(frozen=True)


class Start(_Command):
    kind: Literal["start"] = "start"


class Choose(_Command):
    """A button: an option id, "yes"/"no", "old"/"new"/"neither", or an ISO date choice."""

    kind: Literal["choose"] = "choose"
    option_id: str
    extra_text: str | None = None  # the text box of a free_text option


class Text(_Command):
    kind: Literal["text"] = "text"
    text: str


class Skip(_Command):
    """ "Skip" on optional fields, "Answer later" on needed ones."""

    kind: Literal["skip"] = "skip"


class Pause(_Command):
    kind: Literal["pause"] = "pause"
    resume_code_hash: str = ""  # filled in by the service


class Resume(_Command):
    kind: Literal["resume"] = "resume"


class TalkToPerson(_Command):
    kind: Literal["talk_to_person"] = "talk_to_person"


class ContinueAlone(_Command):
    kind: Literal["continue_alone"] = "continue_alone"


class KeepGoing(_Command):
    kind: Literal["keep_going"] = "keep_going"


class Undo(_Command):
    kind: Literal["undo"] = "undo"


class EditField(_Command):
    kind: Literal["edit_field"] = "edit_field"
    field_id: str


class MarkUnknown(_Command):
    kind: Literal["mark_unknown"] = "mark_unknown"
    field_id: str


class Submit(_Command):
    kind: Literal["submit"] = "submit"


Command = Annotated[
    Start
    | Choose
    | Text
    | Skip
    | Pause
    | Resume
    | TalkToPerson
    | ContinueAlone
    | KeepGoing
    | Undo
    | EditField
    | MarkUnknown
    | Submit,
    Field(discriminator="kind"),
]
