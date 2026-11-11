from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountTests(TestCase):
    def test_signup_cannot_promote_user_and_preserves_safe_next(self):
        response = self.client.post(reverse("signup") + "?next=/registrations/", {"username": "newstudent", "password1": "Useful-demo-secret-42", "password2": "Useful-demo-secret-42", "is_superuser": "true", "is_staff": "true", "groups": "Organizers", "next": "/registrations/"})
        self.assertRedirects(response, "/registrations/")
        user = get_user_model().objects.get(username="newstudent")
        self.assertFalse(user.is_staff or user.is_superuser or user.groups.exists())
        self.assertTrue(user.check_password("Useful-demo-secret-42"))
        self.assertNotEqual(user.password, "Useful-demo-secret-42")

    def test_external_return_url_ignored(self):
        response = self.client.post(reverse("signup"), {"username": "safe", "password1": "Useful-demo-secret-42", "password2": "Useful-demo-secret-42", "next": "https://evil.example/path"})
        self.assertRedirects(response, "/")

    def test_login_invalid_then_valid_and_post_logout(self):
        get_user_model().objects.create_user("student", password="Useful-demo-secret-42")
        self.assertContains(self.client.post(reverse("login"), {"username": "student", "password": "wrong"}), "Please enter a correct")
        self.assertEqual(self.client.post(reverse("login"), {"username": "student", "password": "Useful-demo-secret-42"}).status_code, 302)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)

    def test_csrf_and_login_required(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post(reverse("signup"), {"username": "bad"}).status_code, 403)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("login") + "?next=/organizer/")
        self.assertEqual(self.client.get(reverse("roles")).status_code, 302)
