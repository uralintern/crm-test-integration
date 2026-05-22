from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # username сюда будет приходить как email
        if username is None or password is None:
            return None

        try:
            user = get_user_model().objects.get(email__iexact=str(username).strip())
        except get_user_model().DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
