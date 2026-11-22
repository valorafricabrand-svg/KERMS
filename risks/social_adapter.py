from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import Organization, OrganizationMembership, SignupConsent
from .views import SIGNUP_PRIVACY_VERSION, SIGNUP_TERMS_VERSION


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return settings.PUBLIC_SIGNUP_ENABLED

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        email = (sociallogin.user.email or "").strip().lower()
        if not email:
            return
        existing_user = get_user_model().objects.filter(email__iexact=email).first()
        if existing_user:
            sociallogin.connect(request, existing_user)

    def save_user(self, request, sociallogin, form=None):
        with transaction.atomic():
            user = super().save_user(request, sociallogin, form=form)
            organization = Organization.objects.create(
                name=form.cleaned_data["organization_name"],
                code=form.cleaned_data["organization_code"],
            )
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrganizationMembership.Role.ADMIN,
            )
            SignupConsent.objects.create(
                user=user,
                terms_version=SIGNUP_TERMS_VERSION,
                privacy_version=SIGNUP_PRIVACY_VERSION,
                verified_at=timezone.now(),
            )
            user.is_active = True
            user.save(update_fields=["is_active"])
        return user
