from flask_wtf import FlaskForm
from wtforms import (
    BooleanField, IntegerField, SelectField,
    SelectMultipleField, TextAreaField, SubmitField
)
from wtforms.validators import DataRequired, Optional, NumberRange, ValidationError


class DatingPreferencesForm(FlaskForm):
    enabled = BooleanField('Enable Dating & Matchmaking')
    
    age = IntegerField('Your Age', validators=[
        Optional(),
        NumberRange(min=18, max=120, message="You must be at least 18 years old to participate in dating.")
    ])
    
    gender = SelectField('Your Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('non-binary', 'Non-Binary'),
        ('other', 'Other')
    ], validators=[Optional()])

    interested_in = SelectField('Interested In', choices=[
        ('women', 'Women'),
        ('men', 'Men'),
        ('everyone', 'Everyone'),
        ('non-binary', 'Non-Binary')
    ], default='everyone', validators=[Optional()])

    min_age_pref = IntegerField('Minimum Age Preference', default=18, validators=[
        Optional(),
        NumberRange(min=18, max=120, message="Minimum age preference must be at least 18.")
    ])
    
    max_age_pref = IntegerField('Maximum Age Preference', default=99, validators=[
        Optional(),
        NumberRange(min=18, max=120, message="Maximum age preference must be between 18 and 120.")
    ])

    show_gender = BooleanField('Display gender on your public dating card', default=True)

    bio = TextAreaField('Dating Bio / What you are looking for', validators=[
        Optional()
    ])

    interests = SelectMultipleField('Interests & Hobbies', coerce=int, choices=[])

    submit = SubmitField('Save Dating Preferences')

    def validate_max_age_pref(self, field):
        min_age = self.min_age_pref.data or 18
        if field.data and field.data < min_age:
            raise ValidationError("Maximum age preference cannot be lower than minimum age preference.")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        if self.enabled.data:
            if not self.age.data:
                self.age.errors.append("Age is required to enable the dating feature.")
                return False
            if self.age.data < 18:
                self.age.errors.append("You must be at least 18 years old to use the dating feature.")
                return False
        return True
