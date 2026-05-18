from django import forms
from .models import Vacacion, LicenciaMedica


class VacacionForm(forms.ModelForm):
    class Meta:
        model   = Vacacion
        fields  = ['trabajador', 'inicio', 'fin', 'comentario']
        widgets = {
            'inicio':     forms.DateInput(attrs={'type': 'date', 'class': 'p-input'}),
            'fin':        forms.DateInput(attrs={'type': 'date', 'class': 'p-input'}),
            'comentario': forms.Textarea(attrs={'rows': 2, 'class': 'p-input p-textarea'}),
            'trabajador': forms.Select(attrs={'class': 'p-input p-select'}),
        }


class LicenciaForm(forms.ModelForm):
    class Meta:
        model   = LicenciaMedica
        fields  = ['trabajador', 'inicio', 'fin', 'tipo', 'folio', 'documento']
        widgets = {
            'inicio':     forms.DateInput(attrs={'type': 'date', 'class': 'p-input'}),
            'fin':        forms.DateInput(attrs={'type': 'date', 'class': 'p-input'}),
            'tipo':       forms.Select(attrs={'class': 'p-input p-select'}),
            'trabajador': forms.Select(attrs={'class': 'p-input p-select'}),
            'folio':      forms.TextInput(attrs={'class': 'p-input', 'placeholder': 'Ej: LM-2025-0001'}),
            'documento':  forms.FileInput(attrs={'class': 'p-input'}),
        }
