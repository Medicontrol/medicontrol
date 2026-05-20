from django import forms
from .models import Medicamento, Tratamiento


class MedicamentoForm(forms.ModelForm):
    tratamiento = forms.ModelChoiceField(
        queryset=Tratamiento.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Tratamiento"
    )

    class Meta:
        model = Medicamento
        fields = [
            'nombre', 'descripcion', 'dosis', 'stock',
            'tratamiento', 'fecha_vencimiento', 'frecuencia_horas', 'proxima_toma'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dosis': forms.TextInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'frecuencia_horas': forms.Select(choices=[(i, f'Cada {i} horas') for i in range(1, 25)], attrs={'class': 'form-select'}),
            'proxima_toma': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['tratamiento'].queryset = Tratamiento.objects.filter(usuario=self.user)