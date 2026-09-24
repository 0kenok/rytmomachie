from django import forms
from django.utils.translation import gettext_lazy as _

from . import ai, engine
from .models import Game


class NewGameForm(forms.Form):
    VICTORY_CHOICES = [
        (engine.VICTORY_BODY, _("De corpore: capture a number of pieces")),
        (engine.VICTORY_GOODS, _("De bonis: capture pieces worth a total value")),
        (engine.VICTORY_PROGRESSION, _("Victoria magna: three pieces in progression in the enemy half")),
    ]

    RANDOM = "random"
    SIDE_CHOICES = [
        (engine.WHITE, _("White (you move first)")),
        (engine.BLACK, _("Black")),
        (RANDOM, _("Random")),
    ]

    mode = forms.ChoiceField(choices=Game.MODE_CHOICES, initial=Game.AI, widget=forms.RadioSelect)
    ai_level = forms.TypedChoiceField(
        label=_("Computer level"),
        choices=Game.AI_LEVEL_CHOICES,
        coerce=int,
        initial=ai.MEDIUM,
        required=False,
    )
    side = forms.ChoiceField(label=_("You play"), choices=SIDE_CHOICES, initial=engine.WHITE, required=False)
    victories = forms.MultipleChoiceField(
        label=_("Victory conditions"),
        choices=VICTORY_CHOICES,
        initial=[engine.VICTORY_BODY],
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": _("Choose at least one victory condition.")},
    )
    # Each side has 24 pieces.
    target_body = forms.IntegerField(
        label=_("Pieces to capture"), required=False, min_value=1, max_value=24,
        widget=forms.NumberInput(attrs={"placeholder": engine.VICTORY_DEFAULT_TARGET[engine.VICTORY_BODY]}),
    )
    target_goods = forms.IntegerField(
        label=_("Total value to capture"), required=False, min_value=1, max_value=5000,
        widget=forms.NumberInput(attrs={"placeholder": engine.VICTORY_DEFAULT_TARGET[engine.VICTORY_GOODS]}),
    )

    def clean(self):
        data = super().clean()
        if data.get("mode") == Game.AI:
            data["ai_level"] = data.get("ai_level") or ai.MEDIUM
            data["side"] = data.get("side") or engine.WHITE
        targets = {
            engine.VICTORY_BODY: data.get("target_body"),
            engine.VICTORY_GOODS: data.get("target_goods"),
            engine.VICTORY_PROGRESSION: None,
        }
        # {victory type: target or None for the default}, for engine.new_game().
        data["victory_targets"] = {kind: targets[kind] for kind in data.get("victories", [])}
        return data
