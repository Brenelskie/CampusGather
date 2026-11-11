from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from .models import Organization, Venue, EventCategory, Event, AgendaItem, Registration, Announcement
from .permissions import is_admin, managed_events
from .services import FIELDS, OWNED_MODELS

class ResourceForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        model = self._meta.model
        if model in OWNED_MODELS and is_admin(user) and not self.instance.pk:
            self.fields["owner"] = forms.ModelChoiceField(queryset=get_user_model().objects.filter(Q(is_superuser=True) | Q(groups__name="Organizers")).distinct(), initial=user)
        if model is Event:
            for name, related in [("organization", Organization), ("venue", Venue), ("category", EventCategory)]:
                qs = related.objects.all()
                if not is_admin(user):
                    qs = qs.filter(owner=user)
                elif self.instance.pk:
                    qs = qs.filter(owner=self.instance.organization.owner)
                self.fields[name].queryset = qs
            if self.instance.pk:
                self.fields["organization"].disabled = True
        if model in (AgendaItem, Announcement, Registration):
            self.fields["event"].queryset = managed_events(user) if model is not Registration else Event.objects.filter(status="published", starts_at__gt=timezone.now())
            if self.instance.pk:
                self.fields["event"].queryset = Event.objects.filter(pk=self.instance.event_id)
                self.fields["event"].disabled = True
        for name, field in self.fields.items():
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})
                field.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]
            field.widget.attrs.setdefault("class", "form-control")

def form_for(model):
    return forms.modelform_factory(model, form=ResourceForm, fields=FIELDS[model])

class RegistrationNoteForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ["attendance_note"]
        widgets = {"attendance_note": forms.Textarea(attrs={"rows": 3, "maxlength": 300})}
