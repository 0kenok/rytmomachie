from django import forms
from django.utils.translation import gettext_lazy as _

from . import engine
from .models import Game


class NewGameForm(forms.Form):
    VICTORY_CHOICES = [
        (engine.VICTORY_BODY, _("De corpore: capture a number of pieces")),
        (engine.VICTORY_GOODS, _("De bonis: capture pieces worth a total value")),
        (engine.VICTORY_PROGRESSION, _("Victoria magna: three pieces in progression in the enemy half")),
    ]

    mode = forms.ChoiceField(choices=Game.MODE_CHOICES, initial=Game.LOCAL, widget=forms.RadioSelect)
    victory = forms.ChoiceField(choices=VICTORY_CHOICES, initial=engine.VICTORY_BODY)
    target = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=5000,
        help_text=_("Pieces (de corpore) or total value (de bonis). Leave empty for the default."),
    )
