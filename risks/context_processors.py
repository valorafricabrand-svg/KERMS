from django.conf import settings


def feature_flags(request):
    return {"google_sign_in_enabled": settings.GOOGLE_SIGN_IN_ENABLED}
