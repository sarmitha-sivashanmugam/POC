from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.contrib import messages

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to handle Google OAuth account linking.
    If a user with the same email exists, link the Google account to that user
    instead of trying to create a new account.
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed.
        """
        if sociallogin.is_existing: #if already linked, don't to anything
            return

        # Check if a user with this email already exists
        if sociallogin.account.extra_data.get('email'): #extract email
            email = sociallogin.account.extra_data['email']
            try:
                existing_user = User.objects.get(email=email) #check if the user already exists
                # Link the social account to the existing user
                sociallogin.connect(request, existing_user)
                messages.success(request, f'Successfully linked your Google account to {email}')
            except User.DoesNotExist:
                # No existing user, proceed with normal signup
                pass
