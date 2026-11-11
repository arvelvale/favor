"""Generate a password hash interactively; never accept passwords in command arguments."""
from getpass import getpass

from werkzeug.security import generate_password_hash


def main():
    password = getpass("管理员新密码（至少 12 位）: ")
    if len(password) < 12:
        raise SystemExit("密码至少需要 12 位")
    if password != getpass("再次输入密码: "):
        raise SystemExit("两次密码不一致")
    # Paste this line into .env, not into an interactive shell ($ is part of the hash).
    print("请将下面一行保存到本地 .env，不要提交：")
    print("ADMIN_PASSWORD_HASH='" + generate_password_hash(password) + "'")


if __name__ == "__main__":
    main()
