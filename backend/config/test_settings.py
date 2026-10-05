"""本地/CI 跑测试用：继承正式配置，改用内存 SQLite，无需 Postgres。

用法：python manage.py test --settings=config.test_settings
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
