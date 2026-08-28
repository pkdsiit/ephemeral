from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, Optional, ValidationError
from flask_login import current_user
from app.models.user import User


class UpdateUsernameForm(FlaskForm):
    username = StringField('New Username', validators=[
        DataRequired(message="Username is required."),
        Length(min=3, max=30, message="Username must be between 3 and 30 characters."),
        Regexp(r'^[a-zA-Z0-9_]+$', message="Username may only contain letters, numbers, and underscores.")
    ])
    submit = SubmitField('Update Username')

    def validate_username(self, field):
        new_username = field.data.strip()
        if new_username.lower() == current_user.username.lower():
            return
        if User.query.filter_by(username_lower=new_username.lower()).first():
            raise ValidationError("Username is already taken.")


class UpdateProfileForm(FlaskForm):
    display_name = StringField('Display Name', validators=[
        Optional(),
        Length(max=64, message="Display name must be 64 characters or fewer.")
    ])
    bio = TextAreaField('About You / Bio', validators=[
        Optional(),
        Length(max=500, message="Bio must be 500 characters or fewer.")
    ])
    avatar = FileField('Profile Picture', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only (jpg, png, webp).')
    ])
    submit = SubmitField('Save Profile')


class ReportUserForm(FlaskForm):
    reason = StringField('Reason', validators=[
        DataRequired(message="Please provide a reason for the report."),
        Length(max=255)
    ])
    details = TextAreaField('Additional Details', validators=[
        Optional(),
        Length(max=1000)
    ])
    submit = SubmitField('Submit Report')
