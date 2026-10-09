from datetime import timedelta

import pytest

from iam.domain.model.aggregates.PasswordReset import PasswordReset, utc_now_naive
from iam.domain.model.aggregates.Role import Role, ROLE_ADMIN, ROLE_USER
from iam.domain.model.aggregates.User import User, UserStatus


def make_user(status: UserStatus = UserStatus.PENDING, role_name: str | None = None) -> User:
    user = User(email="a@b.com", hashed_password="hash", full_name="Test", status=status)
    if role_name:
        user.role = Role(id=1, name=role_name)
    return user


class TestPasswordPolicy:
    @pytest.mark.parametrize("password", ["Abcdef1!", "Str0ng#Password", "Zz9$zzzz"])
    def test_accepts_strong_passwords(self, password):
        User.validate_password_policy(password)

    @pytest.mark.parametrize(
        "password, missing",
        [
            ("Ab1!", "at least 8 characters"),
            ("abcdefg1!", "an uppercase letter"),
            ("ABCDEFG1!", "a lowercase letter"),
            ("Abcdefgh!", "a number"),
            ("Abcdefg12", "a special character"),
        ],
    )
    def test_rejects_weak_passwords_and_says_what_is_missing(self, password, missing):
        with pytest.raises(ValueError, match=missing):
            User.validate_password_policy(password)

    def test_hash_is_verifiable_and_never_the_plain_password(self):
        hashed = User.hash_password("Abcdef1!")
        user = User(email="a@b.com", hashed_password=hashed, full_name="T")
        assert hashed != "Abcdef1!"
        assert user.verify_password("Abcdef1!")
        assert not user.verify_password("Other#Pass1")

    def test_hashing_enforces_the_policy(self):
        with pytest.raises(ValueError):
            User.hash_password("weak")


class TestAccountLifecycle:
    def test_approve_activates_and_assigns_the_role(self):
        user = make_user()
        user.approve(Role(id=2, name=ROLE_USER))
        assert user.status == UserStatus.ACTIVE
        assert user.is_engineer() and not user.is_admin()

    def test_reject_marks_the_request_as_rejected(self):
        user = make_user()
        user.reject()
        assert user.status == UserStatus.REJECTED
        assert user.role is None

    @pytest.mark.parametrize("status", [UserStatus.ACTIVE, UserStatus.REJECTED, UserStatus.DISABLED])
    def test_only_pending_requests_can_be_reviewed(self, status):
        with pytest.raises(ValueError):
            make_user(status).approve(Role(id=2, name=ROLE_USER))
        with pytest.raises(ValueError):
            make_user(status).reject()

    def test_disable_and_enable(self):
        user = make_user(UserStatus.ACTIVE, ROLE_USER)
        user.disable()
        assert user.status == UserStatus.DISABLED and not user.can_authenticate()
        user.enable()
        assert user.status == UserStatus.ACTIVE and user.can_authenticate()

    @pytest.mark.parametrize("status", [UserStatus.PENDING, UserStatus.REJECTED, UserStatus.DISABLED])
    def test_only_active_accounts_can_be_disabled(self, status):
        with pytest.raises(ValueError):
            make_user(status).disable()

    @pytest.mark.parametrize("status", [UserStatus.PENDING, UserStatus.REJECTED, UserStatus.ACTIVE])
    def test_only_disabled_accounts_can_be_enabled(self, status):
        with pytest.raises(ValueError):
            make_user(status).enable()

    def test_only_rejected_requests_can_be_resubmitted(self):
        user = make_user(UserStatus.REJECTED)
        user.resubmit("New Name", "new-hash")
        assert user.status == UserStatus.PENDING
        assert (user.full_name, user.hashed_password) == ("New Name", "new-hash")
        with pytest.raises(ValueError):
            make_user(UserStatus.ACTIVE).resubmit("x", "y")

    @pytest.mark.parametrize(
        "status, can_authenticate",
        [
            (UserStatus.ACTIVE, True),
            (UserStatus.PENDING, False),
            (UserStatus.REJECTED, False),
            (UserStatus.DISABLED, False),
        ],
    )
    def test_only_active_accounts_can_authenticate(self, status, can_authenticate):
        assert make_user(status).can_authenticate() is can_authenticate

    def test_role_checks(self):
        assert make_user(role_name=ROLE_ADMIN).is_admin()
        assert not make_user().is_admin() and not make_user().is_engineer()


class TestPasswordReset:
    def test_new_code_has_six_digits_and_is_valid_for_15_minutes(self):
        entry = PasswordReset.issue_for(user_id=1)
        assert len(entry.code) == 6 and entry.code.isdigit()
        assert entry.is_valid(entry.code)
        assert timedelta(minutes=14) < entry.expires_at - utc_now_naive() <= timedelta(minutes=15)

    def test_wrong_expired_or_used_codes_are_invalid(self):
        entry = PasswordReset.issue_for(user_id=1)
        wrong = "000000" if entry.code != "000000" else "111111"
        assert not entry.is_valid(wrong)

        entry.expires_at = utc_now_naive() - timedelta(seconds=1)
        assert entry.is_expired() and not entry.is_valid(entry.code)

        entry.renew()
        entry.mark_used()
        assert not entry.is_valid(entry.code)

    def test_renew_replaces_the_code_and_makes_it_usable_again(self):
        entry = PasswordReset.issue_for(user_id=1)
        entry.mark_used()
        entry.expires_at = utc_now_naive() - timedelta(hours=1)
        entry.renew()
        assert not entry.used and not entry.is_expired()
        assert entry.is_valid(entry.code)
